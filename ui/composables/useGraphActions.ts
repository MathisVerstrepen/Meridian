import type { NodeWithDimensions } from '@/types/graph';
import { MarkerType, useVueFlow } from '@vue-flow/core';

export const useGraphActions = () => {
    const { getBlockById } = useBlocks();
    const { generateId } = useUniqueId();
    const { error } = useToast();

    const placeBlock = (
        graphId: string,
        blocId: string,
        positionFrom: { x: number; y: number },
        positionOffset: { x: number; y: number } = { x: 0, y: 0 },
        center: boolean = false,
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
            id: generateId(),
            type: blockData.nodeType,
            position: {
                x: positionFrom.x + positionOffset.x,
                y: positionFrom.y + positionOffset.y,
            },
            label: blockData.name,
            data: { ...blockData.defaultData },
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
            markerEnd: {
                type: MarkerType.ArrowClosed,
                height: 20,
                width: 20,
            },
        };

        addEdges(newEdge);
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

    return {
        placeBlock,
        placeEdge,
        numberOfConnectionsFromHandle,
    };
};
