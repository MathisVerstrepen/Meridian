import type { NodeWithDimensions } from '@/types/graph';
import {
    useVueFlow,
    type XYPosition,
    type GraphNode,
    type Node,
    type Connection,
} from '@vue-flow/core';

interface PlaceBlockOptions {
    graphId: string;
    blocId: string;
    fromNodeId?: string | null;
    positionFrom: { x: number; y: number };
    positionOffset?: { x: number; y: number };
    center?: boolean;
    data?: Record<string, unknown>;
    forcedId?: string | null;
}

export const useGraphActions = () => {
    const { getBlockById } = useBlocks();
    const { generateId } = useUniqueId();
    const { error, info, warning } = useToast();

    const placeBlock = (options: PlaceBlockOptions) => {
        const { addNodes, getNodes } = useVueFlow('main-graph-' + options.graphId);

        const blockData = getBlockById(options.blocId);
        if (!blockData) {
            console.error(`Block definition not found for ID: ${options.blocId}`);
            error(`Block definition not found for ID: ${options.blocId}`, {
                title: 'Error',
            });
            return;
        }

        options.positionOffset = options.positionOffset || { x: 0, y: 0 };
        if (options.center) {
            options.positionOffset.x -= blockData.minSize.width / 2;
            options.positionOffset.y -= blockData.minSize.height / 2;
        }

        const fromNode = getNodes.value.find((n) => n.id === options.fromNodeId);

        const newNode: NodeWithDimensions = {
            id: options.forcedId || generateId(),
            type: blockData.nodeType,
            position: {
                x: options.positionFrom.x + (options.positionOffset?.x || 0),
                y: options.positionFrom.y + (options.positionOffset?.y || 0),
            },
            label: blockData.name,
            data: { ...blockData.defaultData, ...options.data },
            parentNode: fromNode?.parentNode,
            expandParent: true,
        };

        if (blockData?.forcedInitialDimensions) {
            newNode.width = blockData.minSize.width;
            newNode.height = blockData.minSize.height;
        }

        addNodes(newNode);

        return newNode;
    };

    const placeEdge = (
        graphId: string,
        sourceId: string | undefined,
        targetId: string | undefined,
        sourceHandleId: string | null = null,
        targetHandleId: string | null = null,
    ) => {
        const { addEdges } = useVueFlow('main-graph-' + graphId);

        if (!sourceId || !targetId) {
            console.error('Source or target ID is missing for edge placement.');
            error('Source or target ID is missing for edge placement.', {
                title: 'Error',
            });
            return;
        }

        const newEdge = {
            id: generateId(),
            source: sourceId,
            target: targetId,
            sourceHandle: sourceHandleId,
            targetHandle: targetHandleId,
            type: 'custom',
        };

        addEdges(newEdge);
    };

    const toggleEdgeAnimation = (
        graphId: string,
        animated: boolean,
        sourceId: string | null,
        targetId: string | null,
    ) => {
        const { edges } = useVueFlow('main-graph-' + graphId);

        if (sourceId) {
            edges.value.forEach((edge) => {
                if (edge.source === sourceId && (!targetId || edge.target === targetId)) {
                    edge.animated = animated;
                }
            });
        }

        if (targetId) {
            edges.value.forEach((edge) => {
                if (edge.target === targetId && (!sourceId || edge.source === sourceId)) {
                    edge.animated = animated;
                }
            });
        }
    };

    const numberOfConnectionsFromHandle = (
        graphId: string,
        nodeId: string,
        handleId: string | null = null,
    ) => {
        const { getEdges } = useVueFlow('main-graph-' + graphId);

        return getEdges.value.filter((edge) => {
            const isSource = edge.source === nodeId;
            const isTarget = edge.target === nodeId;
            const isSourceHandle = edge.sourceHandle === handleId;
            const isTargetHandle = edge.targetHandle === handleId;

            return (isSource && isSourceHandle) || (isTarget && isTargetHandle);
        }).length;
    };

    const numberOfConnectedHandles = (graphId: string, nodeId: string) => {
        const { getEdges } = useVueFlow('main-graph-' + graphId);

        return getEdges.value.filter((edge) => {
            const isSource = edge.source === nodeId;
            const isTarget = edge.target === nodeId;

            return (isSource && edge.sourceHandle) || (isTarget && edge.targetHandle);
        }).length;
    };

    const duplicateNode = async (graphId: string, nodeId: string) => {
        const { getNodes, addNodes, removeSelectedNodes } = useVueFlow('main-graph-' + graphId);
        const node = getNodes.value.find((n) => n.id === nodeId);

        if (!node) {
            console.error(`Node not found: ${nodeId}`);
            return;
        }

        // Offset node by a few pixels
        const positionOffset = { x: 25, y: 25 };
        const newNode: Node & { selected?: boolean } = {
            id: generateId(),
            position: {
                x: node.position.x + positionOffset.x,
                y: node.position.y + positionOffset.y,
            },
            style: {
                ...node.style,
            },
            data: {
                ...node.data,
            },
            type: node.type,
            selected: true,
            expandParent: true,
            parentNode: node.parentNode,
        };

        addNodes(newNode);

        // wait for div with data-id=newNode.id to be mounted
        await new Promise((resolve) => {
            const checkNode = () => {
                const exists = document.querySelector(`[data-id="${newNode.id}"]`);
                if (exists) {
                    resolve(true);
                } else {
                    setTimeout(checkNode, 10);
                }
            };
            checkNode();
        });

        // Unselect previously selected node
        removeSelectedNodes([node]);
    };

    const copyNode = async (graphId: string, nodeIds: string[]) => {
        const { getNodes, getEdges } = useVueFlow('main-graph-' + graphId);
        const nodes = getNodes.value.filter((n) => nodeIds.includes(n.id));

        if (nodes.length === 0) {
            console.warn(`No nodes selected or found for copying.`);
            return;
        }

        // For each node id that begin with "group-", all all child nodes are also copied
        const groupNodeIds = nodeIds.filter((id) => id.startsWith('group-'));
        groupNodeIds.forEach((groupId) => {
            const childNodes = getNodes.value.filter((n) => n.parentNode === groupId);
            childNodes.forEach((child) => {
                if (!nodeIds.includes(child.id)) {
                    nodes.push(child);
                    nodeIds.push(child.id);
                }
            });
        });

        // Filter edges to only include those fully within the subgraph of copied nodes
        const edgesToCopy = getEdges.value.filter(
            (edge) => nodeIds.includes(edge.source) && nodeIds.includes(edge.target),
        );

        // Store clean copies of nodes (without changing IDs yet)
        const nodesToStore = nodes.map((node) => ({
            ...node,
            selected: false,
        }));

        // Store clean copies of edges
        const edgesToStore = edgesToCopy.map((edge) => ({
            ...edge,
            selected: false,
        }));

        localStorage.setItem('copiedNode', JSON.stringify(nodesToStore));
        localStorage.setItem('copiedEdge', JSON.stringify(edgesToStore));

        info(`Copied ${nodes.length} nodes and ${edgesToCopy.length} edges`);
    };

    const pasteNodes = async (graphId: string, position: XYPosition) => {
        const { addNodes, addEdges, getSelectedNodes, removeSelectedNodes } = useVueFlow(
            'main-graph-' + graphId,
        );

        const copiedNodesJSON = localStorage.getItem('copiedNode');
        const copiedEdgesJSON = localStorage.getItem('copiedEdge');

        if (!copiedNodesJSON) {
            warning('No nodes found in clipboard');
            return;
        }

        const copiedNodes = JSON.parse(copiedNodesJSON);
        const copiedEdges = JSON.parse(copiedEdgesJSON || '[]');

        if (copiedNodes.length === 0) {
            warning('No nodes copied to clipboard');
            return;
        }

        // Deselect previously selected nodes
        removeSelectedNodes(getSelectedNodes.value);

        // Generate new IDs for the nodes to be pasted
        const oldIdToNewIdMap = new Map<string, string>();
        copiedNodes.forEach((node) => {
            const newId = node.id.startsWith('group-') ? `group-${generateId()}` : generateId();
            oldIdToNewIdMap.set(node.id, newId);
        });

        // Reconstruct nodes with new IDs and update parent references
        const newNodesRaw = copiedNodes.map((node) => {
            const newId = oldIdToNewIdMap.get(node.id)!;
            const newParentId =
                node.parentNode && oldIdToNewIdMap.has(node.parentNode)
                    ? oldIdToNewIdMap.get(node.parentNode)
                    : undefined;

            return {
                ...node,
                id: newId,
                parentNode: newParentId,
                selected: true,
                expandParent: true,
                data: {
                    ...node.data,
                    oldId: node.id,
                },
            };
        });

        // Reconstruct edges with new IDs and mapped source/targets
        const newEdges = copiedEdges.map((edge) => ({
            ...edge,
            id: generateId(),
            source: oldIdToNewIdMap.get(edge.source)!,
            sourceHandle: edge.sourceHandle
                ? edge.sourceHandle.split('_')[0] + '_' + oldIdToNewIdMap.get(edge.source)!
                : undefined,
            target: oldIdToNewIdMap.get(edge.target)!,
            targetHandle: edge.targetHandle
                ? edge.targetHandle.split('_')[0] + '_' + oldIdToNewIdMap.get(edge.target)!
                : undefined,
            selected: false,
        }));

        let newNodes;

        if (newNodesRaw.length > 1) {
            // MULTIPLE NODES: Position the group's center at the cursor

            // Calculate the bounding box of the copied nodes (roots only)
            const roots = newNodesRaw.filter((n) => !n.parentNode);

            const subgraphBounds = {
                minX: Infinity,
                minY: Infinity,
                maxX: -Infinity,
                maxY: -Infinity,
            };

            roots.forEach((node) => {
                subgraphBounds.minX = Math.min(subgraphBounds.minX, node.position.x);
                subgraphBounds.minY = Math.min(subgraphBounds.minY, node.position.y);
                subgraphBounds.maxX = Math.max(
                    subgraphBounds.maxX,
                    node.position.x + (node.dimensions?.width || 0),
                );
                subgraphBounds.maxY = Math.max(
                    subgraphBounds.maxY,
                    node.position.y + (node.dimensions?.height || 0),
                );
            });

            // Find the center of the bounding box
            const subgraphCenterX =
                subgraphBounds.minX + (subgraphBounds.maxX - subgraphBounds.minX) / 2;
            const subgraphCenterY =
                subgraphBounds.minY + (subgraphBounds.maxY - subgraphBounds.minY) / 2;

            // Calculate the offset needed to move the center to the cursor
            const offsetX = position.x - subgraphCenterX;
            const offsetY = position.y - subgraphCenterY;

            // Apply the offset to each root node (children move relative to parent)
            newNodes = newNodesRaw.map((node) => {
                if (!node.parentNode) {
                    return {
                        ...node,
                        position: {
                            x: node.position.x + offsetX,
                            y: node.position.y + offsetY,
                        },
                    };
                }
                return node;
            });
        } else {
            // SINGLE NODE: Position the node's center at the cursor
            const node = newNodesRaw[0];
            newNodes = [
                {
                    ...node,
                    position: {
                        x: position.x - (node.dimensions?.width || 0) / 2,
                        y: position.y - (node.dimensions?.height || 0) / 2,
                    },
                },
            ];
        }

        if (newNodes.length > 0) {
            addNodes(newNodes);
        }
        if (newEdges.length > 0) {
            addEdges(newEdges);
        }
    };

    const createCommentGroup = async (
        graphId: string,
        nodesForMenu: GraphNode[],
        closeMenu: () => void,
    ) => {
        const { addNodes, setNodes, getNodes } = useVueFlow('main-graph-' + graphId);

        if (nodesForMenu.length === 0) {
            console.warn('No nodes selected for grouping.');
            return;
        }

        const nodesToGroup = nodesForMenu;
        closeMenu();

        for (const node of nodesToGroup) {
            if (node.id.startsWith('group-')) {
                console.warn('Cannot group a group node.');
                warning('Cannot group a group node.', {
                    title: 'Warning',
                });
                return;
            }
            if (node.parentNode) {
                console.warn('One of the selected nodes is already in a group.');
                warning('One of the selected nodes is already in a group.', {
                    title: 'Warning',
                });
                return;
            }
        }

        const PADDING = 40;
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;

        nodesToGroup.forEach((node) => {
            const { x, y } = node.position;
            const { width = 0, height = 0 } = node.dimensions;
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + width);
            maxY = Math.max(maxY, y + height);
        });

        const parentPosition = { x: minX - PADDING, y: minY - PADDING };
        const parentWidth = maxX - minX + PADDING * 2;
        const parentHeight = maxY - minY + PADDING * 2;

        const parentNodeId = `group-${generateId()}`;
        const parentNode: Node = {
            id: parentNodeId,
            type: 'group',
            position: parentPosition,
            data: {
                title: 'New Group',
                comment: 'Add a description...',
            },
            style: {
                width: `${parentWidth}px`,
                height: `${parentHeight}px`,
            },
            zIndex: -1,
        };

        addNodes([parentNode]);

        await nextTick();

        const updatedChildren = nodesToGroup.map((node) => {
            return {
                ...node,
                parentNode: parentNodeId,
                expandParent: true,
                position: {
                    x: node.position.x - parentPosition.x,
                    y: node.position.y - parentPosition.y,
                },
            };
        });
        setNodes([
            ...getNodes.value.filter((node) => !nodesToGroup.includes(node)),
            ...updatedChildren,
        ]);
    };

    const deleteCommentGroup = (graphId: string, groupId: string) => {
        const { getNodes, setNodes } = useVueFlow('main-graph-' + graphId);
        const nodes = getNodes.value;
        const groupNode = nodes.find((n) => n.id === groupId);

        if (!groupNode) {
            console.error(`Group node not found: ${groupId}`);
            return;
        }

        const childNodes = nodes.filter((n) => n.parentNode === groupId);

        // Remove parentNode and expandParent from child nodes
        const updatedChildren = childNodes.map((node) => ({
            ...node,
            parentNode: undefined,
            expandParent: false,
            position: {
                x: node.position.x + (groupNode.position.x || 0),
                y: node.position.y + (groupNode.position.y || 0),
            },
        }));

        // Update the nodes in the graph
        setNodes([
            ...nodes.filter((n) => n.id !== groupId && n.parentNode !== groupId),
            ...updatedChildren,
        ]);
    };

    const handleNodeDataUpdate = (graphId: string, nodeId: string, payload: object) => {
        if (!graphId || !nodeId || !payload) {
            console.warn(
                'handleNodeDataUpdate called with missing parameters:',
                graphId,
                nodeId,
                payload,
            );
            return;
        }

        const { getNodes, updateNode } = useVueFlow('main-graph-' + graphId);
        const nodeToUpdate = getNodes.value.find((n: Node) => n.id === nodeId);

        if (nodeToUpdate) {
            const updatedNode = {
                ...nodeToUpdate,
                data: {
                    ...((nodeToUpdate.data as Record<string, unknown>) || {}),
                    ...(payload as Record<string, unknown>),
                },
            };
            updateNode(nodeId, updatedNode);
        } else {
            console.warn(`Received node_data_update for unknown node_id: ${nodeId}`);
        }
    };

    const handleContextMergerPlacement = (
        connection: Connection,
        graphId: string,
        newEdgeId: string,
    ) => {
        const { getNodes, getEdges, removeEdges, addEdges } = useVueFlow('main-graph-' + graphId);

        const targetNode = getNodes.value.find((n) => n.id === connection.target);
        if (!targetNode) {
            addEdges({ ...connection, id: generateId(), type: 'custom' });
            return;
        }

        const isGenerator = ['textToText', 'parallelization', 'routing'].includes(
            targetNode.type as string,
        );
        const isContextHandle = connection.targetHandle?.startsWith('context_');

        if (isGenerator && isContextHandle) {
            const existingEdges = getEdges.value.filter(
                (edge) =>
                    edge.target === connection.target &&
                    edge.targetHandle === connection.targetHandle,
            );

            if (existingEdges.length >= 2) {
                const existingEdge = existingEdges[0];
                const existingSourceNode = getNodes.value.find((n) => n.id === existingEdge.source);

                if (existingSourceNode?.type === 'contextMerger') {
                    // There's already a merger, connect the new edge to it
                    placeEdge(
                        graphId,
                        connection.source,
                        existingSourceNode.id,
                        connection.sourceHandle,
                        `context_${existingSourceNode.id}`,
                    );
                    nextTick(() => {
                        removeEdges([newEdgeId]);
                    });

                    return;
                } else {
                    // This is the second connection, create a new merger node
                    const blockDefinition = getBlockById('primary-context-merger');
                    const mergerWidth = blockDefinition?.minSize?.width || 200;
                    const mergerHeight = blockDefinition?.minSize?.height || 100;

                    const targetNodeDimensions = targetNode.dimensions || {
                        width: 200,
                        height: 100,
                    };

                    const position = {
                        x:
                            targetNode.position.x +
                            targetNodeDimensions.width * 0.65 -
                            mergerWidth / 2,
                        y: targetNode.position.y - mergerHeight - 75,
                    };

                    const newMergerNode = placeBlock({
                        graphId: graphId,
                        blocId: 'primary-context-merger',
                        positionFrom: position,
                        center: false,
                    });

                    if (!newMergerNode) return;

                    // Remove the original edge
                    removeEdges([existingEdge.id]);

                    // Connect original source to the new merger
                    placeEdge(
                        graphId,
                        existingEdge.source,
                        newMergerNode.id,
                        existingEdge.sourceHandle,
                        `context_${newMergerNode.id}`,
                    );

                    // Connect new source to the new merger
                    placeEdge(
                        graphId,
                        connection.source,
                        newMergerNode.id,
                        connection.sourceHandle,
                        `context_${newMergerNode.id}`,
                    );

                    // Connect the new merger to the original target
                    placeEdge(
                        graphId,
                        newMergerNode.id,
                        targetNode.id,
                        `context_${newMergerNode.id}`,
                        connection.targetHandle,
                    );

                    nextTick(() => {
                        removeEdges([newEdgeId]);
                    });

                    return;
                }
            }
        }
    };

    const teleportViewportToNode = async (graphId: string, nodeId: string) => {
        const { getNodes, getViewport, setCenter } = useVueFlow('main-graph-' + graphId);
        const node = getNodes.value.find((n) => n.id === nodeId);
        if (node) {
            const { zoom } = getViewport();
            setCenter(node.position.x, node.position.y, { zoom });
        }
    };

    return {
        placeBlock,
        placeEdge,
        toggleEdgeAnimation,
        numberOfConnectionsFromHandle,
        numberOfConnectedHandles,
        duplicateNode,
        copyNode,
        pasteNodes,
        createCommentGroup,
        deleteCommentGroup,
        handleNodeDataUpdate,
        handleContextMergerPlacement,
        teleportViewportToNode,
    };
};
