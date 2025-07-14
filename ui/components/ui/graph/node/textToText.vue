<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import { AVAILABLE_WHEELS } from '@/constants';
import type { DataTextToText } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals', 'update:canvasName', 'update:deleteNode']);

// --- Stores ---
const chatStore = useChatStore();
const streamStore = useStreamStore();
const canvasSaveStore = useCanvasSaveStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { currentModel, openChatId } = storeToRefs(chatStore);
const { blockSettings, isReady } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { loadAndOpenChat } = chatStore;
const { startStream, setCanvasCallback, removeChatCallback, cancelStream } = streamStore;
const { saveGraph } = canvasSaveStore;

// --- Composables ---
const { getBlockById } = useBlocks();
const { addChunkCallbackBuilder } = useStreamCallbacks();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataTextToText> & { isGraphNameDefault: boolean }>();

// --- Local State ---
const isStreaming = ref(false);
const blockDefinition = getBlockById('primary-model-text-to-text');

// --- Core Logic Functions ---
const addChunk = addChunkCallbackBuilder(
    () => {
        props.data.reply = '';
        isStreaming.value = true;
    },
    async () => {
        isStreaming.value = false;
        await saveGraph();
    },
    (chunk: string) => {
        if (props.data) props.data.reply += chunk;
    },
);

const sendPrompt = async () => {
    if (!props.data) return;

    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);

    const session = await startStream(
        props.id,
        NodeTypeEnum.TEXT_TO_TEXT,
        {
            graph_id: graphId.value,
            node_id: props.id,
            model: props.data.model,
        },
        props.isGraphNameDefault,
    );

    if (props.isGraphNameDefault) {
        emit('update:canvasName', session?.titleResponse);
    }
};

const openChat = async () => {
    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);
    currentModel.value = props.data.model;
    loadAndOpenChat(graphId.value, props.id);
};

const handleCancelStream = async () => {
    if (!props.data) return;
    removeChatCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT);
    await nextTick();
    props.data.reply = '';
    isStreaming.value = false;
    await cancelStream(props.id);
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
        :nodeId="props.id"
    ></NodeResizer>

    <div
        class="bg-olive-grove border-olive-grove-dark flex h-full w-full flex-col rounded-3xl border-2 p-4 pt-3
            text-black shadow-lg"
        :class="{ 'opacity-50': props.dragging, 'animate-pulse': isStreaming }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-7 w-7 opacity-80"
                />
                <span
                    class="dark:text-soft-silk/80 text-anthracite -translate-y-0.5 text-lg font-bold"
                >
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
                        class="dark:text-soft-silk text-anthracite h-5 w-5"
                    />
                </button>

                <!-- More Action Button -->
                <UiGraphNodeUtilsActions
                    theme="light"
                    @update:deleteNode="emit('update:deleteNode', props.id)"
                ></UiGraphNodeUtilsActions>
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
                v-if="!isStreaming"
                @click="sendPrompt"
                :disabled="!props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 dark:text-soft-silk text-anthracite flex h-8
                    w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-2xl transition-all duration-200
                    ease-in-out disabled:cursor-not-allowed disabled:opacity-50"
            >
                <UiIcon name="IconamoonSendFill" class="h-5 w-5 opacity-80" />
            </button>

            <button
                v-else
                @click="handleCancelStream"
                :disabled="!props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 dark:text-soft-silk text-anthracite relative
                    flex h-8 w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-2xl transition-all
                    duration-200 ease-in-out disabled:cursor-not-allowed disabled:opacity-50"
            >
                <UiIcon name="MaterialSymbolsStopRounded" class="h-5 w-5" />
            </button>
        </div>

        <!-- Model Response Area -->
        <UiGraphNodeUtilsTextarea
            :reply="props.data.reply"
            :readonly="true"
            color="olive-grove"
            placeholder="AI response will appear here..."
            :autoscroll="true"
        ></UiGraphNodeUtilsTextarea>
    </div>

    <UiGraphNodeUtilsHandleContext
        v-if="isReady"
        type="target"
        :id="props.id"
        :nodeId="props.id"
        :options="[]"
        :style="{ left: '66%' }"
    ></UiGraphNodeUtilsHandleContext>
    <UiGraphNodeUtilsHandlePrompt type="target" :style="{ left: '33%' }" :id="props.id" />
    <UiGraphNodeUtilsHandleAttachment type="target" :id="props.id" />
    <UiGraphNodeUtilsHandleContext
        v-if="isReady"
        :nodeId="props.id"
        :options="AVAILABLE_WHEELS.filter((wheel) => blockSettings.wheel.includes(wheel.value))"
        type="source"
        :id="props.id"
    ></UiGraphNodeUtilsHandleContext>
</template>
