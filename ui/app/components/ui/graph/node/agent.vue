<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataAgent } from '@/types/graph';
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

// --- State from Stores ---
const { openChatId } = storeToRefs(chatStore);
const { isNodeStreaming } = storeToRefs(streamStore);

// --- Actions/Methods from Stores ---
const { loadAndOpenChat, updateUpcomingModelData } = chatStore;
const { startStream, setCanvasCallback, setOnFinishedCallback, removeChatCallback, cancelStream } =
    streamStore;
const { saveGraph, ensureGraphSaved } = canvasSaveStore;

// --- Composables ---
const { getBlockById } = useBlocks();
const { hasPendingAskUserQuestion } = usePendingToolQuestions();
const nodeRegistry = useNodeRegistry();
const { nodeRef, isVisible } = useNodeVisibility();

// --- Agent ---
const route = useRoute();
const graphId = computed(() => firstRouteString(route.params.id) ?? '');

// --- Props ---
const props = withDefaults(
    defineProps<NodeProps<DataAgent> & { isGraphNameDefault: boolean; presetEditor?: boolean }>(),
    { presetEditor: false },
);

// --- Local State ---
const isStreaming = ref(false);
const protectedMode = ref(false);
const blockDefinition = getBlockById('primary-model-agent');
const streamSession = ref<StreamSession | null>(null);
const isAwaitingUser = computed(() => hasPendingAskUserQuestion(props.data.reply));

// --- Core Logic Functions ---
const addChunk = (chunk: string) => {
    if (props.data) props.data.reply = chunk;
};

const sendPrompt = async () => {
    if (!props.data) return;

    protectedMode.value = true;

    await ensureGraphSaved();

    props.data.reply = '';
    isStreaming.value = true;
    protectedMode.value = false;

    setCanvasCallback(props.id, NodeTypeEnum.AGENT, addChunk);
    setOnFinishedCallback(props.id, NodeTypeEnum.AGENT, (session) => {
        isStreaming.value = false;
        props.data.usageData = session.usageData;
        saveGraph();
    });

    streamSession.value = await startStream(
        props.id,
        NodeTypeEnum.AGENT,
        {
            graph_id: graphId.value,
            node_id: props.id,
            model: props.data.model,
        },
        false,
    );
};

const openChat = async () => {
    setCanvasCallback(props.id, NodeTypeEnum.AGENT, addChunk);
    updateUpcomingModelData(NodeTypeEnum.AGENT, props.data);
    loadAndOpenChat(graphId.value, props.id);
};

const handleCancelStream = async () => {
    if (!props.data) return;
    removeChatCallback(props.id, NodeTypeEnum.AGENT);
    await nextTick();
    isStreaming.value = false;
    await cancelStream(props.id);
};

// --- Lifecycle Hooks ---
onMounted(() => {
    if (props.presetEditor) return;

    // when a new text-to-text node is created in chat view, we attach the
    //  callback so that the text generated in the chat is also displayed in the node
    if (openChatId.value === props.id) {
        setCanvasCallback(props.id, NodeTypeEnum.AGENT, addChunk);
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

if (!props.presetEditor) {
    watch(
        () => isNodeStreaming.value(props.id),
        (streaming) => {
            isStreaming.value = streaming;
        },
        { immediate: true },
    );
}

onUnmounted(() => {
    if (!props.presetEditor) nodeRegistry.unregister(props.id);
});
</script>

<template>
    <NodeResizer
        :is-visible="props.selected"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
        v-if="!props.presetEditor"
        :graph-id="graphId"
        :node-id="props.id"
        :selected="props.selected"
        source="generator"
        :in-group="props.parentNodeId !== undefined"
        @update:delete-node="emit('update:deleteNode', props.id)"
        @update:unlink-node="emit('update:unlinkNode', props.id)"
    />

    <div
        ref="nodeRef"
        class="bg-sunbaked-sand border-obsidian/30 relative z-20 flex h-full w-full flex-col
            rounded-3xl border-2 p-4 pt-3 text-black shadow-lg transition-all duration-200
            ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'animate-pulse': isStreaming,
            'shadow-sunbaked-sand/70 shadow-[0px_0px_15px_3px]!': props.selected,
        }"
        @dblclick="!props.presetEditor && openChat()"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="text-obsidian h-7 w-7 opacity-80"
                />
                <span class="text-obsidian/80 -translate-y-0.5 text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
                <UiGraphNodeUtilsSelectedTools :data="props.data" theme="light" />
            </label>
            <div v-if="!props.presetEditor" class="flex items-center space-x-2">
                <UiGenerationHistoryPopover
                    :graph-id="graphId"
                    :node-id="props.id"
                    refresh-chat-on-restore
                    button-class="hover:bg-sunbaked-sand-dark/50"
                    icon-class="text-obsidian h-5 w-5"
                />

                <!-- Open Chat Button -->
                <button
                    class="hover:bg-sunbaked-sand-dark/50 flex items-center justify-center
                        rounded-lg p-1 transition-colors duration-200 ease-in-out"
                    @click="openChat"
                >
                    <UiIcon name="MaterialSymbolsAndroidChat" class="text-obsidian h-5 w-5" />
                </button>
            </div>
        </div>

        <!-- Block Content -->
        <UiChatUtilsStreamRetryStatus v-if="isVisible" :node-id="props.id" />
        <div v-if="isVisible" class="mb-2 flex h-fit items-center justify-between gap-2">
            <UiLibraryAgentSelection
                :auto-select-tools="data.autoSelectTools"
                compact
                class="min-w-0 flex-1 pr-4"
                :model="props.data.model"
                :selected-tools="props.data.selectedTools ?? []"
                :team-id="props.data.teamId"
                @model="props.data.model = $event"
                @team="props.data.teamId = $event"
            />

            <!-- Send Prompt -->
            <button
                v-if="!props.presetEditor && !isStreaming"
                :disabled="!props.data?.model || !props.data.teamId || protectedMode"
                class="nodrag bg-sunbaked-sand-dark hover:bg-sunbaked-sand-dark/80 text-obsidian
                    flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-2xl
                    transition-all duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
                @click="sendPrompt"
            >
                <UiIcon name="IconamoonSendFill" class="h-5 w-5 opacity-80" />
            </button>

            <button
                v-else-if="!props.presetEditor"
                :disabled="!props.data?.model"
                class="nodrag bg-sunbaked-sand-dark hover:bg-sunbaked-sand-dark/80 text-obsidian
                    relative flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center
                    rounded-2xl transition-all duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
                @click="handleCancelStream"
            >
                <UiIcon name="MaterialSymbolsStopRounded" class="h-5 w-5" />
            </button>
        </div>

        <div
            v-if="isAwaitingUser"
            class="text-obsidian nodrag mb-2 flex items-center gap-2 rounded-xl border
                border-amber-600/30 bg-amber-600/15 px-3 py-2 text-xs"
        >
            <UiIcon name="LucideMessageCircleDashed" class="h-5 w-5 shrink-0 text-amber-700" />
            <div class="min-w-0 flex-1">
                <p class="font-bold">Awaiting user input</p>
                <p class="text-obsidian/70">Answer the question in chat to continue this node.</p>
            </div>
        </div>

        <UiLibraryAgentExecutionSummary
            :node-id="props.id"
            :execution="props.data.agentExecution"
        />
        <!-- Model Response Area -->
        <UiGraphNodeUtilsTextarea
            :reply="props.data.reply"
            :readonly="true"
            color="sunbaked-sand"
            placeholder="AI response will appear here..."
            :autoscroll="true"
            :parse-error="true"
        />
    </div>

    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        type="target"
        :style="{ left: '66%' }"
        :is-dragging="props.dragging"
        :multiple-input="true"
        :is-visible="isVisible"
        :show-quick-workflow-wheel="!props.presetEditor"
    />
    <UiGraphNodeUtilsHandlePrompt
        :id="props.id"
        type="target"
        :style="{ left: '33%' }"
        :is-dragging="props.dragging"
        :is-visible="isVisible"
        :show-quick-workflow-wheel="!props.presetEditor"
    />
    <UiGraphNodeUtilsHandleAttachment
        :id="props.id"
        type="target"
        :is-dragging="props.dragging"
        :is-visible="isVisible"
        :show-quick-workflow-wheel="!props.presetEditor"
    />
    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        type="source"
        :is-dragging="props.dragging"
        :is-visible="isVisible"
        :show-quick-workflow-wheel="!props.presetEditor"
    />
</template>
