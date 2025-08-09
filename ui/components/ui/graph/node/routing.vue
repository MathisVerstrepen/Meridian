<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import { AVAILABLE_WHEELS } from '@/constants';
import type { DataRouting } from '@/types/graph';
import type { Route } from '@/types/settings';
import { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals', 'update:canvasName', 'update:deleteNode']);

// --- Stores ---
const chatStore = useChatStore();
const streamStore = useStreamStore();
const canvasSaveStore = useCanvasSaveStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { currentModel } = storeToRefs(chatStore);
const { blockSettings, isReady, blockRoutingSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { loadAndOpenChat } = chatStore;
const { startStream, setCanvasCallback, removeChatCallback, cancelStream } = streamStore;
const { saveGraph } = canvasSaveStore;

// --- Composables ---
const { getBlockById } = useBlocks();
const { addChunkCallbackBuilder } = useStreamCallbacks();
const { getGenerateRoutingStream } = useAPI();
const nodeRegistry = useNodeRegistry();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataRouting> & { isGraphNameDefault: boolean }>();

// --- Local State ---
const isStreaming = ref(false);
const isFetchingModel = ref(false);
const blockDefinition = getBlockById('primary-model-routing');
const selectedRoute = ref<Route | null>(null);

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

    props.data.model = '';
    props.data.reply = '';
    selectedRoute.value = null;
    isFetchingModel.value = true;
    isStreaming.value = true;

    const routingSession = await startStream(
        props.id,
        NodeTypeEnum.ROUTING,
        {
            graph_id: graphId.value,
            node_id: props.id,
            model: '',
        },
        false,
        getGenerateRoutingStream,
        true,
    );

    // When the routing has been stopped earlier, we should not continue
    if (!isStreaming.value) {
        isFetchingModel.value = false;
        return;
    }

    isFetchingModel.value = false;

    const jsonResponse = JSON.parse(routingSession?.response || '{}');
    props.data.selectedRouteId = jsonResponse?.route || '';
    selectedRoute.value =
        blockRoutingSettings.value.routeGroups
            .find((group) => group.id === props.data.routeGroupId)
            ?.routes.find((route) => route.id === props.data.selectedRouteId) || null;

    props.data.model = selectedRoute.value?.modelId || '';

    setCanvasCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT, addChunk);

    const chatSession = await startStream(
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
        emit('update:canvasName', chatSession?.titleResponse);
    }
};

const openChat = async () => {
    setCanvasCallback(props.id, NodeTypeEnum.ROUTING, addChunk);
    currentModel.value = props.data.model;
    loadAndOpenChat(graphId.value, props.id);
};

const handleCancelStream = async () => {
    if (!props.data) return;
    removeChatCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT);
    await nextTick();
    props.data.reply = '';
    selectedRoute.value = null;
    isStreaming.value = false;
    if (!isFetchingModel.value) {
        await cancelStream(props.id);
    }
};

// --- Watchers ---
watch(
    isReady,
    (ready) => {
        if (ready) {
            selectedRoute.value =
                blockRoutingSettings.value.routeGroups
                    .find((group) => group.id === props.data.routeGroupId)
                    ?.routes.find((route) => route.id === props.data.selectedRouteId) || null;
        }
    },
    { immediate: true },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    nodeRegistry.register(props.id, sendPrompt, handleCancelStream);
});

onUnmounted(() => {
    nodeRegistry.unregister(props.id);
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

    <UiGraphNodeUtilsRunToolbar
        :graphId="graphId"
        :nodeId="props.id"
        :selected="props.selected"
        source="generator"
        @update:deleteNode="emit('update:deleteNode', props.id)"
    ></UiGraphNodeUtilsRunToolbar>

    <div
        class="bg-sunbaked-sand border-obsidian/30 flex h-full w-full flex-col rounded-3xl border-2 p-4 pt-3
            text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'animate-pulse': isStreaming,
            'shadow-sunbaked-sand/70 !shadow-[0px_0px_15px_3px]': props.selected,
        }"
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
            </label>
            <div class="flex items-center space-x-2">
                <!-- Open Chat Button -->
                <button
                    class="hover:bg-sunbaked-sand-dark/50 flex items-center justify-center rounded-lg p-1 transition-colors
                        duration-200 ease-in-out"
                    @click="openChat"
                >
                    <UiIcon name="MaterialSymbolsAndroidChat" class="text-obsidian h-5 w-5" />
                </button>
            </div>
        </div>

        <!-- Block Content -->
        <div class="mb-2 flex h-fit items-center justify-between gap-2">
            <!-- Model Select -->
            <UiGraphNodeUtilsRoutingGroupSelect
                :routingGroupId="props.data.routeGroupId"
                :setRoutingGroupId="
                    (id: string) => {
                        props.data.routeGroupId = id;
                    }
                "
                class="shrink-0"
            ></UiGraphNodeUtilsRoutingGroupSelect>

            <UiGraphNodeUtilsRoutingSelectedModel
                :isFetchingModel="isFetchingModel"
                :selectedRoute="selectedRoute"
            ></UiGraphNodeUtilsRoutingSelectedModel>

            <!-- Send Prompt -->
            <button
                v-if="!isStreaming"
                @click="sendPrompt"
                :disabled="!props.data?.routeGroupId"
                class="nodrag bg-sunbaked-sand-dark hover:bg-sunbaked-sand-dark/80 flex h-8 w-8 flex-shrink-0
                    cursor-pointer items-center justify-center rounded-2xl transition-all duration-200 ease-in-out
                    disabled:cursor-not-allowed disabled:opacity-50"
            >
                <UiIcon name="IconamoonSendFill" class="text-obsidian h-5 w-5 opacity-80" />
            </button>

            <button
                v-else
                @click="handleCancelStream"
                class="nodrag bg-sunbaked-sand-dark hover:bg-sunbaked-sand-dark/80 relative flex h-8 w-8 flex-shrink-0
                    cursor-pointer items-center justify-center rounded-2xl transition-all duration-200 ease-in-out"
            >
                <UiIcon name="MaterialSymbolsStopRounded" class="h-5 w-5" />
            </button>
        </div>

        <!-- Model Response Area -->
        <UiGraphNodeUtilsTextarea
            :reply="props.data.reply"
            :readonly="true"
            color="sunbaked-sand"
            placeholder="AI response will appear here..."
            :autoscroll="true"
        ></UiGraphNodeUtilsTextarea>
    </div>

    <UiGraphNodeUtilsHandleContext
        type="target"
        :id="props.id"
        :nodeId="props.id"
        :options="[]"
        :style="{ left: '66%' }"
        :isDragging="props.dragging"
    ></UiGraphNodeUtilsHandleContext>
    <UiGraphNodeUtilsHandlePrompt
        type="target"
        :style="{ left: '33%' }"
        :id="props.id"
        :isDragging="props.dragging"
    />
    <UiGraphNodeUtilsHandleAttachment type="target" :id="props.id" :isDragging="props.dragging" />
    <UiGraphNodeUtilsHandleContext
        :nodeId="props.id"
        :options="AVAILABLE_WHEELS.filter((wheel) => blockSettings.wheel.includes(wheel.value))"
        type="source"
        :id="props.id"
        :isDragging="props.dragging"
    ></UiGraphNodeUtilsHandleContext>
</template>
