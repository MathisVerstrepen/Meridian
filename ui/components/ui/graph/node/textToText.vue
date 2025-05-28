<script lang="ts" setup>
import { Position, Handle, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';
import type { DataTextToText } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals']);

// --- Stores ---
const chatStore = useChatStore();
const streamStore = useStreamStore();
const canvasSaveStore = useCanvasSaveStore();

// --- State from Stores ---
const { currentModel, openChatId } = storeToRefs(chatStore);

// --- Actions/Methods from Stores ---
const { loadAndOpenChat } = chatStore;
const { startStream, setCanvasCallback } = streamStore;
const { saveGraph } = canvasSaveStore;

// --- Composables ---
const { handleConnectableInputContext, handleConnectableInputPrompt } = useEdgeCompatibility();
const { getBlockById } = useBlocks();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataTextToText>>();

// --- Local State ---
const isStreaming = ref(false);
const blockDefinition = getBlockById('primary-model-text-to-text');

// --- Core Logic Functions ---
const addChunk = (chunk: string) => {
    if (chunk === '[START]') {
        props.data.reply = '';
        isStreaming.value = true;
        return;
    } else if (chunk === '[END]') {
        isStreaming.value = false;
        saveGraph();
        return;
    }

    if (props.data) {
        props.data.reply += chunk;
    }
};

const sendPrompt = async () => {
    if (!props.data) return;

    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);

    await startStream(props.id, NodeTypeEnum.TEXT_TO_TEXT, {
        graph_id: graphId.value,
        node_id: props.id,
        model: props.data.model,
        reasoning: {
            effort: null,
            exclude: false,
        },
        system_prompt: '',
    });
};

const openChat = async () => {
    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);
    currentModel.value = props.data.model;
    loadAndOpenChat(graphId.value, props.id);
};

// --- Lifecycle Hooks ---
onMounted(() => {
    // when a new text-to-text node is created in chat view, we attach the
    //  callback so that the text generated in the chat is also displayed in the node
    if (openChatId.value === props.id) {
        setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);
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
        class="bg-olive-grove border-olive-grove-dark flex h-full w-full flex-col rounded-3xl border-2 p-4 pt-3
            text-black shadow-lg"
        :class="{ 'opacity-50': props.dragging }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon name="FluentCodeText16Filled" class="text-soft-silk h-7 w-7 opacity-80" />
                <span class="text-soft-silk/80 -translate-y-0.5 text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
            <div class="flex items-center space-x-2">
                <!-- Open Chat Button -->
                <button
                    class="hover:bg-olive-grove-dark/50 flex items-center justify-center rounded-lg p-1 transition-colors
                        duration-200 ease-in-out"
                    @click="openChat"
                >
                    <UiIcon
                        name="MaterialSymbolsAndroidChat"
                        class="text-soft-silk h-5 w-5 opacity-80"
                    />
                </button>

                <!-- More Action Button -->
                <button
                    class="hover:bg-obsidian/25 flex flex-shrink-0 cursor-pointer items-center rounded-lg p-1 duration-200"
                >
                    <UiIcon
                        name="Fa6SolidEllipsisVertical"
                        class="text-soft-silk h-5 w-5"
                        aria-hidden="true"
                    />
                </button>
            </div>
        </div>

        <!-- Block Content -->
        <div class="mb-2 flex h-fit items-center justify-between">
            <!-- Model Select -->
            <UiModelsSelect
                :model="props.data.model"
                :setModel="
                    (model: string) => {
                        props.data.model = model;
                    }
                "
                variant="green"
                class="h-8 w-2/3"
            ></UiModelsSelect>

            <!-- Send Prompt -->
            <button
                @click="sendPrompt"
                :disabled="isStreaming || !props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 flex h-8 w-8 flex-shrink-0 cursor-pointer
                    items-center justify-center rounded-2xl transition-all duration-200 ease-in-out
                    disabled:cursor-not-allowed disabled:opacity-50"
            >
                <UiIcon
                    v-if="!isStreaming"
                    name="IconamoonSendFill"
                    class="text-soft-silk h-5 w-5 opacity-80"
                />
                <UiIcon v-else name="LineMdLoadingTwotoneLoop" class="text-soft-silk h-7 w-7" />
            </button>
        </div>

        <!-- Model Response Area -->
        <div class="relative h-full w-full">
            <div
                class="absolute bottom-0 left-0 h-1/4 w-full rounded-b-2xl bg-linear-to-b from-[#545d48]/10
                    to-[#545d48]/100"
            ></div>

            <!-- Expand TextArea button -->
            <button class="absolute right-1 bottom-1 cursor-pointer">
                <UiIcon
                    class="text-soft-silk h-5 w-5 opacity-80"
                    name="MaterialSymbolsExpandContentRounded"
                />
            </button>

            <textarea
                v-model="props.data.reply"
                readonly
                class="text-soft-silk nodrag nowheel hide-scrollbar h-full w-full flex-grow resize-none rounded-2xl
                    bg-[#545d48] px-3 py-2 text-sm focus:ring-0 focus:outline-none"
                placeholder="AI response will appear here..."
            ></textarea>
        </div>
    </div>

    <Handle
        type="target"
        :position="Position.Top"
        :id="'prompt_' + props.id"
        :connectable="handleConnectableInputPrompt"
        style="left: 33%; background: #b2c7db"
        class="handletop"
    />
    <Handle
        type="target"
        :position="Position.Top"
        :id="'context_' + props.id"
        :connectable="handleConnectableInputContext"
        style="left: 66%; background: #e5ca5b"
        class="handletop"
    />
    <Handle
        type="source"
        :position="Position.Bottom"
        style="background: #e5ca5b"
        class="handlebottom"
    />
</template>

<style scoped></style>
