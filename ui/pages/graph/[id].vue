<script lang="ts" setup>
import { ConnectionMode, useVueFlow, type Connection } from '@vue-flow/core';
import { Controls, ControlButton } from '@vue-flow/controls';
import type { Graph, DragZoneHoverEvent } from '@/types/graph';
import { DEFAULT_NODE_ID } from '@/constants';
import { ExecutionPlanDirectionEnum, NodeTypeEnum } from '@/types/enums';

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
const { isCanvasReady, openChatId } = storeToRefs(chatStore);
isCanvasReady.value = false;

// --- Route ---
const route = useRoute();
const graphId = computed(() => route.params.id as string);

// --- Local State ---
const graph = ref<Graph | null>(null);
const graphReady = ref(false);
const isDragging = ref(false);
const isHoverDelete = ref(false);
const isMouseOverRightSidebar = ref(false);
const isMouseOverLeftSidebar = ref(false);
const mousePosition = ref({ x: 0, y: 0 });
let lastSavedData: any;
const currentlyDraggedNodeId = ref<string | null>(null);
const currentHoveredZone = ref<DragZoneHoverEvent | null>(null);

// --- Composables ---
const { checkEdgeCompatibility } = useEdgeCompatibility();
const { onDragOver, onDrop, onDragStopOnDragZone } = useGraphDragAndDrop();
const { getGraphById, updateGraph } = useAPI();
const { generateId } = useUniqueId();
const { createNodeFromVariant } = useGraphChat();
const { mapNodeToNodeRequest, mapEdgeToEdgeRequest } = graphMappers();
const {
    onConnect,
    onConnectEnd,
    connectionStartHandle,
    connectionEndHandle,
    fitView,
    addEdges,
    getNodes,
    getEdges,
    setNodes,
    setEdges,
    removeNodes,
    removeEdges,
    onNodesInitialized,
    onNodeDragStart,
    onNodeDragStop,
    onNodeDrag,
    panBy,
    project,
    addSelectedNodes,
} = useVueFlow('main-graph-' + graphId.value);
const graphEvents = useGraphEvents();
const { error } = useToast();
const { setExecutionPlan } = useExecutionPlan();
const { isSelecting, selectionRect, onSelectionStart } = useGraphSelection(
    getNodes,
    project,
    addSelectedNodes,
    panBy,
    isMouseOverRightSidebar,
    isMouseOverLeftSidebar,
);
const { copyNode, pasteNodes, numberOfConnectedHandles } = useGraphActions();

// --- Computed Properties ---
const isGraphNameDefault = computed(() => {
    return !graph.value?.name || graph.value.name === 'New Canvas';
});

// --- Core Logic Functions ---
const updateGraphHandler = async () => {
    if (!graph.value || !graphId.value || !graph.value.id || graph.value.id !== graphId.value) {
        console.warn('Graph data or ID mismatch, skipping update.');
        return;
    }

    let currentData = {
        graph: graph.value,
        nodes: getNodes.value.map((node) => mapNodeToNodeRequest(node, graphId.value)),
        edges: getEdges.value.map((edge) => mapEdgeToEdgeRequest(edge, graphId.value)),
    };
    currentData = JSON.parse(JSON.stringify(currentData));

    if (isDeepEqual(currentData, lastSavedData)) {
        return;
    }

    try {
        lastSavedData = currentData;
        return updateGraph(graphId.value, currentData);
    } catch (err) {
        console.error('Error updating graph:', err);
        error('Failed to update graph. Please try again.', {
            title: 'Graph Update Error',
        });
    }
};

const updateGraphName = (name: string) => {
    if (graph.value) {
        graphEvents.emit('update-name', {
            graphId: graph.value.id,
            name,
        });
        graph.value.name = name;
    }
};

const deleteNode = (nodeId: string) => {
    if (!nodeId) return;

    removeNodes(getNodes.value.filter((node) => node.id === nodeId));
};

const deleteAllNodes = () => {
    if (getNodes.value.length === 0) return;

    if (
        window.confirm('Are you sure you want to delete all nodes? This action cannot be undone.')
    ) {
        removeNodes(getNodes.value);
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
        setEdges(
            completeGraph.edges.map((edge) => ({
                ...edge,
                type: 'custom',
            })),
        );

        if (completeGraph.nodes.length === 0) {
            firstInit = false;
            setInitDone();
        }

        await nextTick();
    } catch (err) {
        console.error(`Error fetching graph (${id}):`, err);
        error('Failed to load graph. Please check the ID and try again.', {
            title: 'Graph Load Error',
        });
    }
};

const handleKeyDown = (event: KeyboardEvent) => {
    // Prevent node paste if chat is open
    if (openChatId.value) return;

    // Prevent node paste if hovering textarea
    const hoveredElement = document.elementFromPoint(mousePosition.value.x, mousePosition.value.y);
    if (hoveredElement?.classList.contains('nodrag')) return;

    const isCtrlOrCmd = event.ctrlKey || event.metaKey;

    // CTRL/CMD + C
    if (isCtrlOrCmd && event.key === 'c') {
        const selectedNodes = getNodes.value.filter((node) => node.selected);

        event.preventDefault();
        copyNode(
            graphId.value,
            selectedNodes.map((node) => node.id),
        );
    }
    // CTRL/CMD + V
    else if (isCtrlOrCmd && event.key === 'v') {
        event.preventDefault();
        const position = project({
            x: mousePosition.value.x,
            y: mousePosition.value.y,
        });

        pasteNodes(graphId.value, position);
    }
};

const handleMouseMove = (event: MouseEvent) => {
    mousePosition.value = { x: event.clientX, y: event.clientY };
};

// --- Lifecycle Hooks ---
onConnect((connection: Connection) => {
    addEdges({
        ...connection,
        id: generateId(),
        type: 'custom',
    });
});

onConnectEnd(() => {
    if (connectionStartHandle.value && connectionEndHandle.value) {
        const connection: Connection = {
            source: connectionStartHandle.value.nodeId,
            sourceHandle: connectionStartHandle.value.id,
            target: connectionEndHandle.value.nodeId,
            targetHandle: connectionEndHandle.value.id,
        };

        const isValid = checkEdgeCompatibility(connection, getNodes.value, false);

        if (!isValid) {
            checkEdgeCompatibility(connection, getNodes.value, true);
        }
    }
});

let firstInit = true;
onNodesInitialized(async () => {
    if (!firstInit) return;
    nextTick(() => {
        firstInit = false;
        setInitDone();
    });
});

onNodeDragStart(async (nodeDragEvent) => {
    const nodeType = nodeDragEvent.node.type as NodeTypeEnum;

    isDragging.value = true;
    isHoverDelete.value = false;
    currentlyDraggedNodeId.value = nodeDragEvent.node.id;

    const nEdges = numberOfConnectedHandles(graphId.value, nodeDragEvent.node.id);
    if (nEdges === 0) {
        graphEvents.emit('node-drag-start', { nodeType: nodeType });
    }
});

onNodeDragStop(async (event) => {
    if (isHoverDelete.value) {
        deleteNode(event.node.id);
    }

    onDragStopOnDragZone(currentHoveredZone.value, currentlyDraggedNodeId.value);

    isDragging.value = false;
    currentlyDraggedNodeId.value = null;
    currentHoveredZone.value = null;

    graphEvents.emit('node-drag-end', {});
});

onNodeDrag((event) => {
    const target = event.event.target as HTMLElement;
    if (target && target.classList.contains('node-trash')) {
        isHoverDelete.value = true;
    } else {
        isHoverDelete.value = false;
    }
});

onMounted(async () => {
    // Subscribe to graph events
    const unsubscribeNodeCreate = graphEvents.on(
        'node-create',
        async ({ variant, fromNodeId }: { variant: string; fromNodeId: string }) => {
            createNodeFromVariant(variant, fromNodeId);
        },
    );

    const unsubscribeDragZoneHover = graphEvents.on('drag-zone-hover', (hoverData) => {
        currentHoveredZone.value = hoverData;
    });

    const unsubscribeEnterHistorySidebar = graphEvents.on(
        'enter-history-sidebar',
        ({ over }: { over: boolean }) => {
            isMouseOverLeftSidebar.value = over;
        },
    );

    setInit();
    await fetchGraph(graphId.value);
    isCanvasReady.value = true;

    await nextTick();

    setTimeout(() => {
        fitView({
            maxZoom: 1,
            minZoom: 0.4,
            padding: 0.2,
        }).then(() => {
            graphReady.value = true;
        });
    }, 0);

    // Ensure all edges are not animated on initial load
    setEdges(
        getEdges.value.map((edge) => ({
            ...edge,
            animated: false,
        })),
    );

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousemove', handleMouseMove);

    onUnmounted(() => {
        unsubscribeNodeCreate();
        unsubscribeDragZoneHover();
        unsubscribeEnterHistorySidebar();
    });
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
    document.removeEventListener('mousemove', handleMouseMove);
});
</script>

<template>
    <div
        class="h-full w-full"
        id="graph-container"
        @dragover="onDragOver"
        @drop="onDrop"
        @mousedown.right="onSelectionStart"
        @contextmenu.prevent
    >
        <ClientOnly>
            <VueFlow
                :fit-view-on-init="false"
                :connection-mode="ConnectionMode.Strict"
                :id="'main-graph-' + graphId"
                :min-zoom="0.1"
                :class="{
                    hideNode: !graphReady,
                }"
                :connection-radius="50"
                auto-connect
                :is-valid-connection="
                    (connection) => checkEdgeCompatibility(connection, getNodes, false)
                "
            >
                <UiGraphBackground pattern-color="var(--color-stone-gray)" :gap="16" />

                <Controls position="top-left" class="!top-2 !z-10 !m-0">
                    <div class="flex items-center gap-2 px-1">
                        <hr class="bg-soft-silk/20 h-5 w-[3px] rounded-full text-transparent" />
                    </div>

                    <ControlButton
                        @click="deleteAllNodes"
                        :disabled="getNodes.length === 0"
                        title="Delete all nodes"
                    >
                        <UiIcon
                            name="MaterialSymbolsDeleteRounded"
                            class="text-stone-gray absolute shrink-0 scale-125"
                        />
                    </ControlButton>

                    <ControlButton
                        @click="
                            setExecutionPlan(
                                graphId,
                                DEFAULT_NODE_ID,
                                ExecutionPlanDirectionEnum.ALL,
                            )
                        "
                        :disabled="getNodes.length === 0"
                        title="Run all nodes"
                    >
                        <UiIcon
                            name="CodiconRunAll"
                            class="text-stone-gray absolute shrink-0 scale-125"
                        />
                    </ControlButton>
                </Controls>

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
                <template #node-routing="routingNodeProps">
                    <UiGraphNodeRouting
                        v-bind="routingNodeProps"
                        :isGraphNameDefault="isGraphNameDefault"
                        @update:canvas-name="updateGraphName"
                        @update:delete-node="deleteNode"
                    />
                </template>

                <template #edge-custom="customEdgeProps">
                    <UiGraphEdgesEdgeCustom
                        v-bind="customEdgeProps"
                        @update:removeEdges="removeEdges"
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

    <UiGraphSidebarWrapper
        :graph="graph"
        @mouseenter="isMouseOverRightSidebar = true"
        @mouseleave="isMouseOverRightSidebar = false"
    />

    <UiGraphSaveCron :updateGraphHandler="updateGraphHandler"></UiGraphSaveCron>

    <UiChatBox :isGraphNameDefault="isGraphNameDefault" @update:canvas-name="updateGraphName" />

    <UiChatNodeTrash v-if="isDragging" :is-hover-delete="isHoverDelete" />

    <div
        class="absolute top-2 left-1/2 z-10 flex w-[25%] -translate-x-1/2 flex-col items-center gap-5"
    >
        <UiGraphExecutionPlan v-if="graphReady" :graphId="graphId" />

        <UiGraphSelectedMenu
            v-if="graphReady"
            :nSelected="getNodes.filter((n) => n.selected).length"
            @update:delete-node="
                () => {
                    getNodes.filter((n) => n.selected).forEach((node) => deleteNode(node.id));
                }
            "
            @update:executionPlan="
                () => {
                    const selectedNodeIds = getNodes
                        .filter((n) => n.selected)
                        .map((node) => node.id)
                        .join(',');
                    setExecutionPlan(graphId, selectedNodeIds, ExecutionPlanDirectionEnum.MULTIPLE);
                }
            "
        />
    </div>

    <!-- Selection Rectangle -->
    <div
        v-if="isSelecting"
        class="pointer-events-none fixed border-2 border-dashed border-blue-500 bg-blue-500/20"
        :style="{
            left: `${selectionRect.x}px`,
            top: `${selectionRect.y}px`,
            width: `${selectionRect.width}px`,
            height: `${selectionRect.height}px`,
        }"
    ></div>
</template>

<style>
.hideNode .vue-flow__pane {
    opacity: 0;
}

.vue-flow__node.dragging {
    pointer-events: none !important;
}
</style>
