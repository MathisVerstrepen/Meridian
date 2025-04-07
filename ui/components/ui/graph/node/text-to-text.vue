<script lang="ts" setup>
import { Position, Handle, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';
import type { GenerateRequest } from '@/types/chat';
import { SavingStatus } from '@/types/enums';

const { handleConnectableInputContext, handleConnectableInputPrompt } = useEdgeCompatibility();

const route = useRoute();
const { id } = route.params as { id: string };

const { openChatFromNodeId } = useChatStore();
const { setNeedSave } = useCanvasSaveStore();

const { getGenerateStream } = useAPI();
const { getBlockById } = useBlocks();
const blockDefinition = getBlockById('primary-model-text-to-text');

const props = defineProps<NodeProps>();

const emit = defineEmits(['updateNodeInternals']);

const selectOptions = [
    { value: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
    { value: 'deepseek/deepseek-chat-v3-0324', label: 'DeepSeek Chat V3' },
    { value: 'deepseek/deepseek-r1', label: 'DeepSeek R1' },
];

const isLoading = ref(false);

const addChunk = (chunk: string) => {
    if (props.data) {
        props.data.reply += chunk;
    }
};

const sendPrompt = async () => {
    if (!props.data) return;

    isLoading.value = true;
    props.data.reply = '';

    getGenerateStream(
        {
            graph_id: id,
            node_id: props.id,
            model: props.data.model,
        } as GenerateRequest,
        addChunk,
    ).then(() => {
        setNeedSave(SavingStatus.NOT_SAVED);
        isLoading.value = false;
    });
};
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
                <Icon
                    name="fluent:code-text-16-filled"
                    style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                    class="opacity-80"
                />
                <span class="text-soft-silk/80 -translate-y-[1px] font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
            <button
                class="hover:bg-olive-grove-dark/50 flex items-center justify-center rounded-lg p-1 transition-colors
                    duration-200 ease-in-out"
                @click="openChatFromNodeId(id, props.id)"
            >
                <Icon
                    name="material-symbols:android-chat"
                    style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                    class="opacity-80"
                />
            </button>
        </div>

        <div class="mb-4 flex h-fit items-center justify-center space-x-1">
            <select
                v-model="props.data.model"
                class="nodrag bg-olive-grove-dark text-soft-silk/80 h-10 w-full rounded-lg px-4 font-bold focus:ring-0
                    focus:outline-none"
                @change="setNeedSave(SavingStatus.NOT_SAVED)"
            >
                <option v-for="option in selectOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                </option>
            </select>

            <button
                @click="sendPrompt"
                :disabled="isLoading || !props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 flex h-10 w-10 flex-shrink-0 items-center
                    justify-center rounded-lg transition-all duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
            >
                <Icon
                    v-if="!isLoading"
                    name="lets-icons:send-hor-duotone-line"
                    style="color: var(--color-soft-silk); height: 1.75rem; width: 1.75rem"
                    class="opacity-80"
                />
                <Icon
                    v-else
                    name="line-md:loading-twotone-loop"
                    style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                />
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
