<script lang="ts" setup>
import { ConnectionMode, useVueFlow, MarkerType, type Connection } from '@vue-flow/core';
import { Controls } from '@vue-flow/controls';
import type { Graph } from '@/types/graph';

// --- Page Meta ---
definePageMeta({ layout: 'canvas', middleware: 'auth' });
useHead({
    title: 'Meridian - Graph',
});

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();
const chatStore = useChatStore();

// --- Actions/Methods from Stores ---
const { setInitDone, setInit } = canvasSaveStore;
const { isCanvasReady } = storeToRefs(chatStore);
isCanvasReady.value = false;

// --- Route ---
const route = useRoute();
const graphId = computed(() => route.params.id as string);

// --- Composables ---
const { checkEdgeCompatibility } = useEdgeCompatibility();
const { onDragOver, onDrop } = useGraphDragAndDrop();
const { getGraphById, updateGraph } = useAPI();
const { generateId } = useUniqueId();
const { createNodeFromVariant } = useGraphChat();
const {
    onConnect,
    fitView,
    addEdges,
    getNodes,
    getEdges,
    setNodes,
    setEdges,
    removeNodes,
    onNodesInitialized,
} = useVueFlow('main-graph-' + graphId.value);
const graphEvents = useGraphEvents();

// --- Local State ---
const graph = ref<Graph | null>(null);
const graphReady = ref(false);

const isGraphNameDefault = computed(() => {
    return !graph.value?.name || graph.value.name === 'New Canvas';
});

// --- Core Logic Functions ---
const updateGraphHandler = async () => {
    if (!graph.value || !graphId.value || !graph.value.id || graph.value.id !== graphId.value) {
        console.warn('Graph data or ID mismatch, skipping update.');
        return;
    }

    try {
        return updateGraph(graphId.value, {
            graph: graph.value,
            nodes: getNodes.value,
            edges: getEdges.value,
        });
    } catch (error) {
        console.error('Error updating graph:', error);
    }
};

const updateGraphName = (name: string) => {
    if (graph.value) {
        graphEvents.emit('update-name', {
            graphId: graph.value.id,
            name,
        });
    }
};

const deleteNode = (nodeId: string) => {
    if (!nodeId) return;

    removeNodes(getNodes.value.filter((node) => node.id === nodeId));
};

const fetchGraph = async (id: string) => {
    graph.value = null;
    setNodes([]);
    setEdges([]);

    try {
        const completeGraph = await getGraphById(id);

        graph.value = completeGraph.graph;
        setNodes(completeGraph.nodes);
        setEdges(completeGraph.edges);

        await nextTick();
    } catch (error) {
        console.error(`Error fetching graph (${id}):`, error);
    }
};

// --- Lifecycle Hooks ---
onConnect((connection: Connection) => {
    if (!checkEdgeCompatibility(connection, getNodes)) {
        console.warn('Edge is not compatible');
        return;
    }

    addEdges({
        ...connection,
        id: generateId(),
        markerEnd: {
            type: MarkerType.ArrowClosed,
            height: 20,
            width: 20,
        },
    });
});

onNodesInitialized(async () => {
    nextTick(() => {
        setInitDone();
    });
});

onMounted(async () => {
    const unsubscribe = graphEvents.on(
        'node-create',
        async ({ variant, fromNodeId }: { variant: string; fromNodeId: string }) => {
            createNodeFromVariant(variant, fromNodeId);
        },
    );

    onUnmounted(unsubscribe);

    setInit();
    await fetchGraph(graphId.value);
    isCanvasReady.value = true;

    await nextTick();

    setTimeout(() => {
        fitView({
            maxZoom: 1,
            padding: 0.2,
        }).then(() => {
            graphReady.value = true;
        });
    }, 0);
});
</script>

<template>
    <div class="h-full w-full" id="graph-container" @dragover="onDragOver" @drop="onDrop">
        <ClientOnly>
            <VueFlow
                :fit-view-on-init="false"
                :connection-mode="ConnectionMode.Strict"
                :id="'main-graph-' + graphId"
                :min-zoom="0.1"
                :class="{
                    hideNode: !graphReady,
                }"
            >
                <UiGraphBackground pattern-color="var(--color-stone-gray)" :gap="16" />

                <Controls position="top-left" />

                <template #node-prompt="promptNodeProps">
                    <UiGraphNodePrompt v-bind="promptNodeProps" @update:delete-node="deleteNode" />
                </template>
                <template #node-filePrompt="filePromptNodeProps">
                    <UiGraphNodeFilePrompt
                        v-bind="filePromptNodeProps"
                        @update:delete-node="deleteNode"
                    />
                </template>
                <template #node-textToText="textToTextNodeProps">
                    <UiGraphNodeTextToText
                        v-bind="textToTextNodeProps"
                        :isGraphNameDefault="isGraphNameDefault"
                        @update:canvas-name="updateGraphName"
                        @update:delete-node="deleteNode"
                    />
                </template>
                <template #node-parallelization="parallelizationNodeProps">
                    <UiGraphNodeParallelization
                        v-bind="parallelizationNodeProps"
                        :isGraphNameDefault="isGraphNameDefault"
                        @update:canvas-name="updateGraphName"
                        @update:delete-node="deleteNode"
                    />
                </template>
            </VueFlow>

            <template #fallback>
                <div class="text-soft-silk flex h-full items-center justify-center">
                    <div class="flex flex-col items-center gap-4">
                        <div
                            class="border-soft-silk h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
                        ></div>
                        <span class="z-10">Loading diagram...</span>
                    </div>
                </div>
            </template>
        </ClientOnly>
    </div>

    <UiGraphSidebarWrapper :graph="graph" />

    <UiGraphSaveCron :updateGraphHandler="updateGraphHandler"></UiGraphSaveCron>

    <UiChatBox :isGraphNameDefault="isGraphNameDefault" @update:canvas-name="updateGraphName" />
</template>

<style>
.hideNode .vue-flow__pane {
    opacity: 0;
}
</style>
