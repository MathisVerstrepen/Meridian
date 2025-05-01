<script lang="ts" setup>
import { Position, Handle, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

const chatStore = useChatStore();
const { fromNodeId, currentModel } = storeToRefs(chatStore);
const { loadAndOpenChat } = chatStore;

const { handleConnectableInputContext, handleConnectableInputPrompt } = useEdgeCompatibility();

const route = useRoute();
const { id } = route.params as { id: string };

const { startStream, setCanvasCallback } = useStreamStore();
const { getBlockById } = useBlocks();
const blockDefinition = getBlockById('primary-model-text-to-text');

const props = defineProps<NodeProps>();

const emit = defineEmits(['updateNodeInternals']);

const isStreaming = ref(false);

const addChunk = (chunk: string) => {
    if (chunk === '[START]') {
        props.data.reply = '';
        return;
    }
    if (props.data) {
        props.data.reply += chunk;
    }
};

const sendPrompt = async () => {
    if (!props.data) return;

    setCanvasCallback(props.id, addChunk);

    props.data.reply = '';
    isStreaming.value = true;

    await startStream(props.id, {
        graph_id: id,
        node_id: props.id,
        model: props.data.model,
    });

    isStreaming.value = false;
};

const openChat = async () => {
    setCanvasCallback(props.id, addChunk);
    currentModel.value = props.data.model;
    loadAndOpenChat(id, props.id);
};

onMounted(() => {
    if (fromNodeId.value === props.id) {
        setCanvasCallback(props.id, addChunk);
    }
});
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="blockDefinition?.minSize?.height"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-olive-grove border-olive-grove-dark flex h-full w-full flex-col rounded-xl border-2 p-4 pt-3
            text-black shadow-lg"
        :class="{ 'opacity-50': props.dragging }"
    >
        <!-- <p class="text-sm text-gray-500">{{ props.id }}</p> -->
        <div class="mb-3 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon name="FluentCodeText16Filled" class="text-soft-silk h-6 w-6 opacity-80" />
                <span class="text-soft-silk/80 -translate-y-[1px] font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
            <button
                class="hover:bg-olive-grove-dark/50 flex items-center justify-center rounded-lg p-1 transition-colors
                    duration-200 ease-in-out"
                @click="openChat"
            >
                <UiIcon
                    name="MaterialSymbolsAndroidChat"
                    class="text-soft-silk h-6 w-6 opacity-80"
                />
            </button>
        </div>

        <div class="mb-4 flex h-fit items-center justify-center space-x-1">
            <UiModelsSelect
                :model="props.data.model"
                :setModel="
                    (model: string) => {
                        props.data.model = model;
                    }
                "
            ></UiModelsSelect>

            <button
                @click="sendPrompt"
                :disabled="isStreaming || !props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 flex h-10 w-10 flex-shrink-0 items-center
                    justify-center rounded-lg transition-all duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
            >
                <UiIcon
                    v-if="!isStreaming"
                    name="LetsIconsSendHorDuotoneLine"
                    class="text-soft-silk h-7 w-7 opacity-80"
                />
                <UiIcon v-else name="LineMdLoadingTwotoneLoop" class="text-soft-silk h-7 w-7" />
            </button>
        </div>

        <textarea
            v-model="props.data.reply"
            readonly
            class="bg-soft-silk/50 nowheel w-full flex-grow resize-none rounded-lg p-2 text-sm focus:ring-0
                focus:outline-none"
            placeholder="AI response will appear here..."
        ></textarea>
    </div>

    <Handle
        type="target"
        :position="Position.Top"
        :id="'prompt_' + props.id"
        :connectable="handleConnectableInputPrompt"
        style="left: 33%; background: var(--color-slate-blue-dark)"
    />
    <Handle
        type="target"
        :position="Position.Top"
        :id="'context_' + props.id"
        :connectable="handleConnectableInputContext"
        style="left: 66%; background: var(--color-golden-ochre)"
    />
    <Handle
        type="source"
        :position="Position.Bottom"
        style="background: var(--color-golden-ochre)"
    />
</template>

<style scoped></style>
