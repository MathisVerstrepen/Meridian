import { useVueFlow, type GraphNode, type HandleElement } from '@vue-flow/core';

export interface SnappedHandle {
    nodeId: string;
    handleId: string;
    position: { x: number; y: number };
    type: 'source' | 'target';
}

export interface ConnectionSource {
    nodeId: string;
    handleId: string;
    type: 'source' | 'target';
}

export const useEdgeSnapping = () => {
    const snappedHandle = useState<SnappedHandle | null>('meridian-snapped-handle', () => null);
    const connectionSource = useState<ConnectionSource | null>(
        'meridian-connection-source',
        () => null,
    );

    const { checkEdgeCompatibility, acceptMultipleInputEdges } = useEdgeCompatibility();
    const { numberOfConnectionsFromHandle } = useGraphActions();

    const startSnapping = (params: {
        nodeId: string;
        handleId: string;
        handleType: 'source' | 'target';
    }) => {
        connectionSource.value = {
            nodeId: params.nodeId,
            handleId: params.handleId,
            type: params.handleType,
        };
    };

    const stopSnapping = () => {
        snappedHandle.value = null;
        connectionSource.value = null;
    };

    const getAbsolutePosition = (node: GraphNode, getNodes: GraphNode[]) => {
        let x = node.position.x;
        let y = node.position.y;
        let parentId = node.parentNode;

        while (parentId) {
            const parent = getNodes.find((n) => n.id === parentId);
            if (parent) {
                x += parent.position.x;
                y += parent.position.y;
                parentId = parent.parentNode;
            } else {
                parentId = undefined;
            }
        }
        return { x, y };
    };

    const findNearestHandle = (mousePos: { x: number; y: number }, graphId: string) => {
        if (!connectionSource.value) return;

        const { getNodes } = useVueFlow('main-graph-' + graphId);
        const nodes = getNodes.value;
        const sourceNodeId = connectionSource.value.nodeId;
        const sourceType = connectionSource.value.type;

        let closestDist = Infinity;
        let closestHandle: SnappedHandle | null = null;

        // Iterate all nodes
        for (const node of nodes) {
            if (node.id === sourceNodeId || !node.handleBounds) continue;

            const targetType = sourceType === 'source' ? 'target' : 'source';
            const handles = node.handleBounds[targetType] as HandleElement[] | undefined;

            if (!handles) continue;

            const nodeAbsPos = getAbsolutePosition(node, nodes);

            for (const handle of handles) {
                // Check compatibility
                const connection = {
                    source: sourceType === 'source' ? sourceNodeId : node.id,
                    target: sourceType === 'source' ? node.id : sourceNodeId,
                    sourceHandle:
                        sourceType === 'source' ? connectionSource.value.handleId : handle.id,
                    targetHandle:
                        sourceType === 'source' ? handle.id : connectionSource.value.handleId,
                };

                // Skip if types are incompatible
                if (!checkEdgeCompatibility(connection, nodes, false)) continue;

                // Check if target handle is full (only relevant if we are connecting TO a target)
                if (sourceType === 'source') {
                    const handleCategory = handle.id.split('_')[0];
                    const isMultipleAccepted = acceptMultipleInputEdges[handleCategory];

                    if (!isMultipleAccepted) {
                        console.log('Checking connections for handle:', graphId, node.id, handle.id);
                        const count = numberOfConnectionsFromHandle(graphId, node.id, handle.id);
                        if (count > 0) continue;
                    }
                }

                // Calculate Distance
                const handleX = nodeAbsPos.x + handle.x + handle.width / 2;
                const handleY = nodeAbsPos.y + handle.y + handle.height / 2;

                const dist = Math.sqrt(
                    Math.pow(mousePos.x - handleX, 2) + Math.pow(mousePos.y - handleY, 2),
                );

                if (dist < closestDist) {
                    closestDist = dist;
                    closestHandle = {
                        nodeId: node.id,
                        handleId: handle.id,
                        position: { x: handleX, y: handleY },
                        type: handle.type,
                    };
                }
            }
        }

        if (snappedHandle.value?.handleId !== closestHandle?.handleId) {
            snappedHandle.value = closestHandle;
        }
    };

    return {
        snappedHandle,
        connectionSource,
        startSnapping,
        stopSnapping,
        findNearestHandle,
    };
};
