import type { NodeWithDimensions } from '@/types/graph';
import { useVueFlow, type XYPosition } from '@vue-flow/core';

export const useGraphActions = () => {
    const { getBlockById } = useBlocks();
    const { generateId } = useUniqueId();
    const { error, info, warning } = useToast();

    const placeBlock = (
        graphId: string,
        blocId: string,
        positionFrom: { x: number; y: number },
        positionOffset: { x: number; y: number } = { x: 0, y: 0 },
        center: boolean = false,
        data: Record<string, any> = {},
        forcedId: string | null = null
    ) => {
        const { addNodes } = useVueFlow('main-graph-' + graphId);

        const blockData = getBlockById(blocId);
        if (!blockData) {
            console.error(`Block definition not found for ID: ${blocId}`);
            error(`Block definition not found for ID: ${blocId}`, {
                title: 'Error',
            });
            return;
        }

        if (center) {
            positionOffset.x -= blockData.minSize.width / 2;
            positionOffset.y -= blockData.minSize.height / 2;
        }

        const newNode: NodeWithDimensions = {
            id: forcedId || generateId(),
            type: blockData.nodeType,
            position: {
                x: positionFrom.x + positionOffset.x,
                y: positionFrom.y + positionOffset.y,
            },
            label: blockData.name,
            data: { ...blockData.defaultData, ...data },
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
        const newNode = {
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

        // Create copies of the nodes
        const newNodes = nodes.map((node) => ({
            id: generateId(),
            position: {
                x: node.position.x,
                y: node.position.y,
            },
            style: {
                ...node.style,
            },
            data: {
                ...node.data,
                oldId: node.id,
            },
            dimensions: {
                width: node.dimensions.width,
                height: node.dimensions.height,
            },
            type: node.type,
            selected: true,
        }));

        const oldIdToNewIdMap = new Map<string, string>();
        newNodes.forEach((node) => {
            if (node.data.oldId) {
                oldIdToNewIdMap.set(node.data.oldId, node.id);
            }
        });

        // Filter edges to only include those fully within the subgraph of copied nodes
        const edgesToCopy = getEdges.value.filter(
            (edge) => nodeIds.includes(edge.source) && nodeIds.includes(edge.target),
        );

        // Create new edges, remapping their source and target to the new node IDs
        const newEdges = edgesToCopy.map((edge) => ({
            ...edge,
            id: generateId(),
            source: oldIdToNewIdMap.get(edge.source)!,
            target: oldIdToNewIdMap.get(edge.target)!,
            selected: false,
        }));

        localStorage.setItem('copiedNode', JSON.stringify(newNodes));
        localStorage.setItem('copiedEdge', JSON.stringify(newEdges));

        info(`Copied ${newNodes.length} nodes and ${newEdges.length} edges`);
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

        let newNodes;

        if (copiedNodes.length > 1) {
            // MULTIPLE NODES: Position the group's center at the cursor

            // Calculate the bounding box of the copied nodes
            const subgraphBounds = {
                minX: Infinity,
                minY: Infinity,
                maxX: -Infinity,
                maxY: -Infinity,
            };

            copiedNodes.forEach((node: any) => {
                subgraphBounds.minX = Math.min(subgraphBounds.minX, node.position.x);
                subgraphBounds.minY = Math.min(subgraphBounds.minY, node.position.y);
                subgraphBounds.maxX = Math.max(
                    subgraphBounds.maxX,
                    node.position.x + node.dimensions.width,
                );
                subgraphBounds.maxY = Math.max(
                    subgraphBounds.maxY,
                    node.position.y + node.dimensions.height,
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

            // Apply the offset to each node
            newNodes = copiedNodes.map((node: any) => ({
                ...node,
                position: {
                    x: node.position.x + offsetX,
                    y: node.position.y + offsetY,
                },
                selected: true,
            }));
        } else {
            // SINGLE NODE: Position the node's center at the cursor
            const node = copiedNodes[0];
            newNodes = [
                {
                    ...node,
                    id: generateId(),
                    position: {
                        x: position.x - node.dimensions.width / 2,
                        y: position.y - node.dimensions.height / 2,
                    },
                    selected: true,
                },
            ];
        }

        if (newNodes.length > 0) {
            addNodes(newNodes);
        }
        if (copiedEdges.length > 0) {
            addEdges(copiedEdges);
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
    };
};
