<script lang="ts" setup>
import type { Connection } from "@vue-flow/core";
import { VueFlow, useVueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import type { Graph } from "@/types/graph";

const { onConnect, addEdges, vueFlowRef, getNodes, getEdges } = useVueFlow();

const { nodes, edges } = useGraphInitializer(vueFlowRef);
const { onDragOver, onDrop } = useGraphDragAndDrop();
const { getGraphById, updateGraph } = useAPI();

const route = useRoute();
const { id } = route.params as { id: string };

const graph = ref<Graph | null>(null);

onConnect((connection: Connection) => {
    addEdges(connection);
});

const updateGraphHandler = async () => {
    try {
        if (!graph.value) {
            console.error("Graph is not initialized");
            return;
        }
        await updateGraph(id, {
            graph: graph.value,
            nodes: getNodes.value,
            edges: getEdges.value,
        });
    } catch (error) {
        console.error("Error updating graph:", error);
    }
};

const fetchGraph = async () => {
    try {
        const graphId = id;
        if (graphId) {
            const completeGraph = await getGraphById(graphId);
            nodes.value = completeGraph.nodes;
            edges.value = completeGraph.edges;
            graph.value = completeGraph.graph;
        } else {
            console.error("Graph not found");
        }
    } catch (error) {
        console.error("Error refreshing graph:", error);
    }
};

onMounted(() => {
    fetchGraph();
});
</script>

<template>
    <div class="flex items-center justify-center h-full w-full relative">
        <div
            class="h-full w-full rounded-lg shadow-lg bg-white"
            id="graph-container"
            @dragover="onDragOver"
            @drop="onDrop"
        >
            <client-only>
                <VueFlow
                    :nodes="nodes"
                    :edges="edges"
                    :fit-view-on-init="false"
                    class="rounded-lg"
                >
                    <Background pattern-color="#aaa" :gap="16" />
                    <Controls position="top-left" />

                    <template #node-prompt="promptNodeProps">
                        <UiGraphNodePrompt v-bind="promptNodeProps" />
                    </template>
                    <template #node-textToText="textToTextNodeProps">
                        <UiGraphNodeTextToText v-bind="textToTextNodeProps" />
                    </template>
                </VueFlow>
                <template #fallback>
                    <div class="flex items-center justify-center h-full">
                        Loading diagram...
                    </div>
                </template>
            </client-only>
        </div>

        <UiGraphSidebarSelector />

        <div class="absolute bottom-0 left-0 p-4 flex space-x-4">
            <button
                class="bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg"
                @click="updateGraphHandler"
            >
                Save
            </button>

            <button
                class="bg-amber-500 text-white px-4 py-2 rounded-lg shadow-lg"
                @click="fetchGraph"
            >
                Refresh
            </button>
        </div>
    </div>
</template>

<style scoped></style>
