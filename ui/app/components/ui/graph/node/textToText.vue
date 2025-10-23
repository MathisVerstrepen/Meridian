<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataTextToText } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits([
    'updateNodeInternals',
    'update:canvasName',
    'update:deleteNode',
    'update:unlinkNode',
]);

// --- Stores ---
const chatStore = useChatStore();
const streamStore = useStreamStore();
const canvasSaveStore = useCanvasSaveStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { openChatId } = storeToRefs(chatStore);
const { blockSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { loadAndOpenChat, updateUpcomingModelData } = chatStore;
const { startStream, setCanvasCallback, setOnFinishedCallback, removeChatCallback, cancelStream } =
    streamStore;
const { saveGraph, ensureGraphSaved } = canvasSaveStore;

// --- Composables ---
const { getBlockById } = useBlocks();
const nodeRegistry = useNodeRegistry();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataTextToText> & { isGraphNameDefault: boolean }>();

// --- Local State ---
const isStreaming = ref(false);
const blockDefinition = getBlockById('primary-model-text-to-text');
const streamSession = ref<StreamSession | null>(null);

// --- Core Logic Functions ---
const addChunk = (chunk: string) => {
    if (props.data) props.data.reply += chunk;
};

const sendPrompt = async () => {
    if (!props.data) return;

    await ensureGraphSaved();

    props.data.reply = '';
    isStreaming.value = true;

    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);
    setOnFinishedCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, (session) => {
        isStreaming.value = false;
        props.data.usageData = session.usageData;
        saveGraph();
    });

    streamSession.value = await startStream(
        props.id,
        NodeTypeEnum.TEXT_TO_TEXT,
        {
            graph_id: graphId.value,
            node_id: props.id,
            model: props.data.model,
        },
        props.isGraphNameDefault,
    );
};

const openChat = async () => {
    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);
    updateUpcomingModelData(
        NodeTypeEnum.TEXT_TO_TEXT,
        props.data as unknown as Record<string, unknown>,
    );
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

    nodeRegistry.register(props.id, sendPrompt, handleCancelStream, streamSession);

    if (props.isGraphNameDefault) {
        watch(
            () => streamSession.value?.titleResponse,
            (newTitle) => {
                if (props.isGraphNameDefault && newTitle) {
                    emit('update:canvasName', newTitle);
                }
            },
        );
    }
});

onUnmounted(() => {
    nodeRegistry.unregister(props.id);
});
</script>

<template>
    <NodeResizer
        :is-visible="true"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
        :graph-id="graphId"
        :node-id="props.id"
        :selected="props.selected"
        source="generator"
        :in-group="props.parentNodeId !== undefined"
        @update:delete-node="emit('update:deleteNode', props.id)"
        @update:unlink-node="emit('update:unlinkNode', props.id)"
    />

    <div
        class="bg-olive-grove border-olive-grove-dark flex h-full w-full flex-col rounded-3xl
            border-2 p-4 pt-3 text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'animate-pulse': isStreaming,
            'shadow-olive-grove-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
        @dblclick="openChat"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-7 w-7 opacity-80"
                />
                <span
                    class="dark:text-soft-silk/80 text-anthracite -translate-y-0.5 text-lg
                        font-bold"
                >
                    {{ blockDefinition?.name }}
                </span>
                <UiGraphNodeUtilsSelectedTools :data="props.data" />
            </label>
            <div class="flex items-center space-x-2">
                <!-- Open Chat Button -->
                <button
                    class="hover:bg-olive-grove-dark/50 flex items-center justify-center rounded-lg
                        p-1 transition-colors duration-200 ease-in-out"
                    @click="openChat"
                >
                    <UiIcon
                        name="MaterialSymbolsAndroidChat"
                        class="dark:text-soft-silk text-anthracite h-5 w-5"
                    />
                </button>
            </div>
        </div>

        <!-- Block Content -->
        <div class="mb-2 flex h-fit items-center justify-between">
            <!-- Model Select -->
            <UiModelsSelect
                :model="props.data.model"
                :set-model="
                    (model: string) => {
                        props.data.model = model;
                    }
                "
                :disabled="false"
                to="left"
                variant="green"
                class="h-8 w-2/3"
                prevent-trigger-on-mount
                :pin-exacto-models="props.data.selectedTools?.length > 0"
            />

            <!-- Send Prompt -->
            <button
                v-if="!isStreaming"
                :disabled="!props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 dark:text-soft-silk
                    text-anthracite flex h-8 w-8 flex-shrink-0 cursor-pointer items-center
                    justify-center rounded-2xl transition-all duration-200 ease-in-out
                    disabled:cursor-not-allowed disabled:opacity-50"
                @click="sendPrompt"
            >
                <UiIcon name="IconamoonSendFill" class="h-5 w-5 opacity-80" />
            </button>

            <button
                v-else
                :disabled="!props.data?.model"
                class="nodrag bg-olive-grove-dark hover:bg-olive-grove-dark/80 dark:text-soft-silk
                    text-anthracite relative flex h-8 w-8 flex-shrink-0 cursor-pointer items-center
                    justify-center rounded-2xl transition-all duration-200 ease-in-out
                    disabled:cursor-not-allowed disabled:opacity-50"
                @click="handleCancelStream"
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
            :parse-error="true"
        />
    </div>

    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        type="target"
        :node-id="props.id"
        :options="[]"
        :style="{ left: '66%' }"
        :is-dragging="props.dragging"
    />
    <UiGraphNodeUtilsHandlePrompt
        :id="props.id"
        type="target"
        :style="{ left: '33%' }"
        :is-dragging="props.dragging"
    />
    <UiGraphNodeUtilsHandleAttachment :id="props.id" type="target" :is-dragging="props.dragging" />
    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        :node-id="props.id"
        :options="blockSettings.contextWheel"
        type="source"
        :is-dragging="props.dragging"
    />
</template>
