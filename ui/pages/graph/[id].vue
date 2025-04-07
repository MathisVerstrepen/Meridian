<script lang="ts" setup>
import { ConnectionMode, VueFlow, useVueFlow, MarkerType, type Connection } from '@vue-flow/core';
import { Controls } from '@vue-flow/controls';
import type { Graph } from '@/types/graph';

const canvasSaveStore = useCanvasSaveStore();

const { onDragOver, onDrop } = useGraphDragAndDrop();
const { getGraphById, updateGraph } = useAPI();
const { checkEdgeCompatibility } = useEdgeCompatibility();
const { generateId } = useUniqueNodeId();

const route = useRoute();
const graphId = computed(() => route.params.id as string);

const { onConnect, fitView, addEdges, getNodes, getEdges, setNodes, setEdges } = useVueFlow(
    'main-graph-' + graphId.value,
);

const graph = ref<Graph | null>(null);

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

const updateGraphHandler = async () => {
    try {
        if (!graph.value) {
            console.error('Graph is not initialized');
            return;
        }
        if (!graph.value.id || !graphId.value) return;
        await updateGraph(graphId.value, {
            graph: graph.value,
            nodes: getNodes.value,
            edges: getEdges.value,
        });
    } catch (error) {
        console.error('Error updating graph:', error);
    }
};

const fetchGraph = async (graphId: string) => {
    try {
        if (graphId) {
            const completeGraph = await getGraphById(graphId);
            setNodes(completeGraph.nodes);
            setEdges(completeGraph.edges);
            graph.value = completeGraph.graph;

            setTimeout(() => {
                canvasSaveStore.setInitDone();
            }, 1000);
        } else {
            console.error('Graph not found');
        }
    } catch (error) {
        console.error('Error refreshing graph:', error);
    }
};

watch(
    graphId,
    (newId, oldId) => {
        if (newId && newId !== oldId) {
            fetchGraph(newId).then(() => {
                setTimeout(() => {
                    fitView({
                        maxZoom: 1,
                    });
                }, 0);
            });
        }
    },
    { immediate: true },
);
</script>

<template>
    <div class="h-full w-full" id="graph-container" @dragover="onDragOver" @drop="onDrop">
        <client-only>
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
        </client-only>
    </div>

    <UiGraphSaveCron :updateGraphHandler="updateGraphHandler"></UiGraphSaveCron>
</template>

<style scoped></style>
