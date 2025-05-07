<script lang="ts" setup>
import { ConnectionMode, useVueFlow, MarkerType, type Connection } from '@vue-flow/core';
import { Controls } from '@vue-flow/controls';
import type { Graph } from '@/types/graph';

// --- Page Meta ---
definePageMeta({ layout: 'canvas' });
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
const { generateId } = useUniqueNodeId();
const { onConnect, fitView, addEdges, getNodes, getEdges, setNodes, setEdges, onPaneReady } =
    useVueFlow('main-graph-' + graphId.value);

// --- Local State ---
const graph = ref<Graph | null>(null);

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

onPaneReady(async () => {
    await fitView({
        maxZoom: 1,
    });

    setTimeout(() => {
        setInitDone();
    }, 100);
});

onMounted(async () => {
    setInit();
    await fetchGraph(graphId.value);
    isCanvasReady.value = true;
});
</script>

<template>
    <div class="h-full w-full" id="graph-container" @dragover="onDragOver" @drop="onDrop">
        <ClientOnly>
            <VueFlow
                :fit-view-on-init="false"
                :connection-mode="ConnectionMode.Strict"
                :id="'main-graph-' + graphId"
                class="rounded-lg"
            >
                <UiGraphBackground pattern-color="var(--color-stone-gray)" :gap="16" />

                <Controls position="top-left" />

                <template #node-prompt="promptNodeProps">
                    <UiGraphNodePrompt v-bind="promptNodeProps" />
                </template>
                <template #node-textToText="textToTextNodeProps">
                    <UiGraphNodeTextToText v-bind="textToTextNodeProps" />
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

    <UiGraphSaveCron :updateGraphHandler="updateGraphHandler"></UiGraphSaveCron>
</template>

<style scoped></style>
