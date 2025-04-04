<script lang="ts" setup>
import { ConnectionMode, VueFlow, useVueFlow, MarkerType, type Connection } from '@vue-flow/core';
import { Controls } from '@vue-flow/controls';
import { SavingStatus } from '@/types/enums';
import type { Graph } from '@/types/graph';

const { onConnect, addEdges, fitView, vueFlowRef, getNodes, getEdges } = useVueFlow();

const { nodes, edges } = useGraphInitializer(vueFlowRef);
const { onDragOver, onDrop } = useGraphDragAndDrop();
const { getGraphById, updateGraph } = useAPI();
const { checkEdgeCompatibility } = useEdgeCompatibility();

const route = useRoute();
const currentGraphId = computed(() => route.params.id as string);

const graph = ref<Graph | null>(null);
const needSave = ref<SavingStatus>(SavingStatus.INIT);

onConnect((connection: Connection) => {
    if (!checkEdgeCompatibility(connection, getNodes)) {
        console.warn('Edge is not compatible');
        return;
    }

    addEdges({
        ...connection,
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
        if (!graph.value.id || !currentGraphId.value) return;
        await updateGraph(currentGraphId.value, {
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
            nodes.value = completeGraph.nodes;
            edges.value = completeGraph.edges;
            graph.value = completeGraph.graph;

            setTimeout(() => {
                needSave.value = SavingStatus.SAVED;
            }, 1000);
        } else {
            console.error('Graph not found');
        }
    } catch (error) {
        console.error('Error refreshing graph:', error);
    }
};

const setNeedSave = (value: SavingStatus) => {
    if (needSave.value !== SavingStatus.INIT) {
        needSave.value = value;
    }
};

const getNeedSave = () => {
    return needSave.value;
};

watch(
    currentGraphId,
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
                :nodes="nodes"
                :edges="edges"
                :fit-view-on-init="false"
                :connection-mode="ConnectionMode.Strict"
                class="rounded-lg"
                @nodes-change="setNeedSave(SavingStatus.NOT_SAVED)"
                @edges-change="setNeedSave(SavingStatus.NOT_SAVED)"
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

    <UiGraphSaveCron
        :updateGraphHandler="updateGraphHandler"
        :setNeedSave="setNeedSave"
        :getNeedSave="getNeedSave"
    ></UiGraphSaveCron>
</template>

<style scoped></style>
