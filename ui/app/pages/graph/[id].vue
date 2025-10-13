<script lang="ts" setup>
import { ConnectionMode, useVueFlow, type Connection, VueFlow } from '@vue-flow/core';
import type { Graph, DragZoneHoverEvent, NodeRequest, EdgeRequest } from '@/types/graph';
import type { NodeTypeEnum } from '@/types/enums';
import { ExecutionPlanDirectionEnum } from '@/types/enums';

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
let lastSavedData: { graph: Graph; nodes: NodeRequest[]; edges: EdgeRequest[] } | null = null;
const currentlyDraggedNodeId = ref<string | null>(null);
const currentHoveredZone = ref<DragZoneHoverEvent | null>(null);
const isTemporaryGraph = computed(() => route.query.temporary === 'true');
const selectedRightTabGroup = ref(0);

let unsubscribeNodeCreate: (() => void) | null = null;
let unsubscribeDragZoneHover: (() => void) | null = null;
let unsubscribeEnterHistorySidebar: (() => void) | null = null;

// --- Composables ---
const { checkEdgeCompatibility } = useEdgeCompatibility();
const { onDragOver, onDrop, onDragStopOnDragZone, onDragStopOnGroupNode } = useGraphDragAndDrop();
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
const { error, warning } = useToast();
const { setExecutionPlan } = useExecutionPlan();
const { isSelecting, selectionRect, onSelectionStart, menuPosition, nodesForMenu, closeMenu } =
    useGraphSelection(
        getNodes,
        project,
        addSelectedNodes,
        panBy,
        isMouseOverRightSidebar,
        isMouseOverLeftSidebar,
    );

const { copyNode, pasteNodes, numberOfConnectedHandles, createCommentGroup, deleteCommentGroup } =
    useGraphActions();

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
        await updateGraph(graphId.value, currentData);
    } catch (err) {
        console.error('Error updating graph:', err);
        error('Failed to update graph. Please try again.', {
            title: 'Graph Update Error',
        });
    }
};

const updateGraphName = (name: string) => {
    if (graph.value && name) {
        if (name.includes('[ERROR]')) {
            warning('Error while generating graph name.');
            return;
        }
        graphEvents.emit('update-name', {
            graphId: graph.value.id,
            name,
        });
        graph.value.name = name;
    }
};

const deleteNode = (nodeId: string) => {
    if (!nodeId) return;

    nodesForMenu.value = [];

    removeNodes(getNodes.value.filter((node) => node.id === nodeId));
};

const unlinkNodeFromGroup = (nodeId: string) => {
    if (!nodeId) return;

    const node = getNodes.value.find((n) => n.id === nodeId);
    if (node && node.parentNode) {
        const parentNode = getNodes.value.find((n) => n.id === node.parentNode);
        const updatedNode = {
            ...node,
            parentNode: undefined,
            expandParent: false,
            position: {
                x: node.position.x + (parentNode?.position.x || 0),
                y: node.position.y + (parentNode?.position.y || 0),
            },
        };
        setNodes([...getNodes.value.filter((n) => n.id !== nodeId), updatedNode]);
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

    // Check if the currently focused element is a textarea, input, or has nodrag class
    const activeElement = document.activeElement;
    if (activeElement) {
        if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
            return;
        }

        let element = activeElement as HTMLElement;
        while (element) {
            if (element.classList?.contains('nodrag')) {
                return;
            }
            element = element.parentElement as HTMLElement;
        }
    }

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
    // DELETE key
    else if (event.key === 'Delete' || event.keyCode === 46 || event.key === 'Backspace') {
        const selectedNodes = getNodes.value.filter((node) => node.selected);
        if (selectedNodes.length > 0) {
            event.preventDefault();
            for (const node of selectedNodes) {
                if (node.id.startsWith('group-')) {
                    deleteCommentGroup(graphId.value, node.id);
                } else {
                    deleteNode(node.id);
                }
            }
        }
    }
};

const handleMouseMove = (event: MouseEvent) => {
    mousePosition.value = { x: event.clientX, y: event.clientY };
};

// --- Watchers ---
watch(
    () => openChatId.value,
    (newVal) => {
        selectedRightTabGroup.value = newVal ? 1 : 0;
    },
);

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

    graphEvents.emit('node-drag-start', { nodeType: nodeType, nEdges: nEdges });
});

onNodeDragStop(async (event) => {
    if (isHoverDelete.value) {
        deleteNode(event.node.id);
    }

    onDragStopOnDragZone(currentHoveredZone.value, currentlyDraggedNodeId.value);
    onDragStopOnGroupNode(currentlyDraggedNodeId.value);

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
    unsubscribeNodeCreate = graphEvents.on(
        'node-create',
        async ({
            variant,
            fromNodeId,
            options,
        }: {
            variant: NodeTypeEnum;
            fromNodeId: string;
            options?: NodeTypeEnum[] | undefined;
        }) => {
            createNodeFromVariant(variant, fromNodeId, options);
        },
    );

    unsubscribeDragZoneHover = graphEvents.on('drag-zone-hover', (hoverData) => {
        currentHoveredZone.value = hoverData;
    });

    unsubscribeEnterHistorySidebar = graphEvents.on(
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
});

onUnmounted(() => {
    if (unsubscribeNodeCreate) unsubscribeNodeCreate();
    if (unsubscribeDragZoneHover) unsubscribeDragZoneHover();
    if (unsubscribeEnterHistorySidebar) unsubscribeEnterHistorySidebar();

    document.removeEventListener('keydown', handleKeyDown);
    document.removeEventListener('mousemove', handleMouseMove);
});
</script>

<template>
    <div
        id="graph-container"
        class="h-full w-full"
        @dragover="onDragOver"
        @drop="onDrop"
        @mousedown.right="onSelectionStart"
        @contextmenu.prevent
    >
        <ClientOnly>
            <VueFlow
                :id="'main-graph-' + graphId"
                :fit-view-on-init="false"
                :connection-mode="ConnectionMode.Strict"
                :min-zoom="0.1"
                :class="{
                    hideNode: !graphReady,
                    'opacity-0': isTemporaryGraph,
                }"
                :connection-radius="50"
                auto-connect
                :is-valid-connection="
                    (connection) => checkEdgeCompatibility(connection, getNodes, false)
                "
                :delete-key-code="null"
            >
                <UiGraphBackground pattern-color="var(--color-stone-gray)" :gap="16" />

                <UiGraphCanvasControls :graph-id="graphId" />

                <template #node-prompt="promptNodeProps">
                    <UiGraphNodePrompt
                        v-bind="promptNodeProps"
                        @update:delete-node="deleteNode"
                        @update:unlink-node="unlinkNodeFromGroup"
                    />
                </template>
                <template #node-filePrompt="filePromptNodeProps">
                    <UiGraphNodeFilePrompt
                        v-bind="filePromptNodeProps"
                        @update:delete-node="deleteNode"
                        @update:unlink-node="unlinkNodeFromGroup"
                    />
                </template>
                <template #node-github="githubNodeProps">
                    <UiGraphNodeGithub
                        v-bind="githubNodeProps"
                        @update:delete-node="deleteNode"
                        @update:unlink-node="unlinkNodeFromGroup"
                    />
                </template>
                <template #node-textToText="textToTextNodeProps">
                    <UiGraphNodeTextToText
                        v-bind="textToTextNodeProps"
                        :is-graph-name-default="isGraphNameDefault"
                        @update:canvas-name="updateGraphName"
                        @update:delete-node="deleteNode"
                        @update:unlink-node="unlinkNodeFromGroup"
                    />
                </template>
                <template #node-parallelization="parallelizationNodeProps">
                    <UiGraphNodeParallelization
                        v-bind="parallelizationNodeProps"
                        :is-graph-name-default="isGraphNameDefault"
                        @update:canvas-name="updateGraphName"
                        @update:delete-node="deleteNode"
                        @update:unlink-node="unlinkNodeFromGroup"
                    />
                </template>
                <template #node-routing="routingNodeProps">
                    <UiGraphNodeRouting
                        v-bind="routingNodeProps"
                        :is-graph-name-default="isGraphNameDefault"
                        @update:canvas-name="updateGraphName"
                        @update:delete-node="deleteNode"
                        @update:unlink-node="unlinkNodeFromGroup"
                    />
                </template>
                <template #node-group="groupNodeProps">
                    <UiGraphNodeGroup
                        v-bind="groupNodeProps"
                        @update:delete-node="deleteCommentGroup"
                    />
                </template>

                <template #edge-custom="customEdgeProps">
                    <UiGraphEdgesEdgeCustom
                        v-bind="customEdgeProps"
                        @update:remove-edges="removeEdges"
                    />
                </template>
            </VueFlow>

            <template #fallback>
                <div class="text-soft-silk flex h-full items-center justify-center">
                    <div class="flex flex-col items-center gap-4">
                        <div
                            class="border-soft-silk h-8 w-8 animate-spin rounded-full border-4
                                border-t-transparent"
                        />
                        <span class="z-10">Loading diagram...</span>
                    </div>
                </div>
            </template>
        </ClientOnly>
    </div>

    <UiGraphSidebarWrapper
        v-model:selected-tab="selectedRightTabGroup"
        :graph="graph"
        :is-temporary="isTemporaryGraph"
        @mouseenter="isMouseOverRightSidebar = true"
        @mouseleave="isMouseOverRightSidebar = false"
    />

    <UiGraphSaveCron :update-graph-handler="updateGraphHandler" />

    <UiChatBox :is-graph-name-default="isGraphNameDefault" @update:canvas-name="updateGraphName" />

    <UiChatNodeTrash v-if="isDragging" :is-hover-delete="isHoverDelete" />

    <div
        class="absolute top-2 left-1/2 z-10 flex w-[25%] -translate-x-1/2 flex-col items-center
            gap-5"
    >
        <UiGraphExecutionPlan v-if="graphReady" :graph-id="graphId" />

        <UiGraphSelectedMenu
            v-if="graphReady"
            :n-selected="getNodes.filter((n) => n.selected).length"
            @update:delete-node="
                () => {
                    getNodes.filter((n) => n.selected).forEach((node) => deleteNode(node.id));
                }
            "
            @update:execution-plan="
                () => {
                    const selectedNodeIds = getNodes
                        .filter((n) => n.selected)
                        .map((node) => node.id)
                        .join(',');
                    setExecutionPlan(graphId, selectedNodeIds, ExecutionPlanDirectionEnum.MULTIPLE);
                }
            "
            @create-group="
                createCommentGroup(
                    graphId,
                    getNodes.filter((n) => n.selected),
                    closeMenu,
                )
            "
            @update:unlink-node="
                () => {
                    getNodes
                        .filter((n) => n.selected)
                        .forEach((node) => unlinkNodeFromGroup(node.id));
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
    />

    <UiGraphNodeUtilsGroupMenu
        v-if="menuPosition"
        :position="menuPosition"
        @create-group="createCommentGroup(graphId, nodesForMenu, closeMenu)"
        @mouseleave="closeMenu"
    />
</template>

<style>
.hideNode .vue-flow__pane {
    opacity: 0;
}

.vue-flow__node.dragging {
    pointer-events: none !important;
}
</style>
