import { useVueFlow, type GraphNode, type HandleElement } from '@vue-flow/core';
import { SpatialBucketIndex } from '@/utils/spatialIndex';

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

type SnapCandidate = SnappedHandle;

export const useEdgeSnapping = () => {
    const snappedHandle = useState<SnappedHandle | null>('meridian-snapped-handle', () => null);
    const connectionSource = useState<ConnectionSource | null>(
        'meridian-connection-source',
        () => null,
    );

    const { acceptsMultipleInputEdges } = useEdgeCompatibility();
    let snapCandidateIndex: SpatialBucketIndex<SnapCandidate> | null = null;
    const pendingMousePosition = useState<{ x: number; y: number } | null>(
        'meridian-pending-snap-mouse-position',
        () => null,
    );
    const pendingGraphId = useState<string | null>('meridian-pending-snap-graph-id', () => null);
    const animationFrameId = useState<number | null>('meridian-snap-frame-id', () => null);

    const getHandleCategory = (handleId?: string | null) => handleId?.split('_')[0] ?? '';

    const resetPendingSearch = () => {
        pendingMousePosition.value = null;
        pendingGraphId.value = null;

        if (animationFrameId.value !== null && typeof window !== 'undefined') {
            window.cancelAnimationFrame(animationFrameId.value);
        }

        animationFrameId.value = null;
    };

    const startSnapping = (params: {
        nodeId: string;
        handleId: string;
        handleType: 'source' | 'target';
        graphId?: string;
    }) => {
        connectionSource.value = {
            nodeId: params.nodeId,
            handleId: params.handleId,
            type: params.handleType,
        };

        resetPendingSearch();
        snapCandidateIndex = params.graphId ? buildSnapCandidateIndex(params.graphId) : null;
    };

    const stopSnapping = () => {
        resetPendingSearch();
        snapCandidateIndex = null;
        snappedHandle.value = null;
        connectionSource.value = null;
    };

    const getAbsolutePosition = (
        node: GraphNode,
        nodeMap: Map<string, GraphNode>,
        absolutePositionCache: Map<string, { x: number; y: number }>,
    ) => {
        const cachedPosition = absolutePositionCache.get(node.id);
        if (cachedPosition) {
            return cachedPosition;
        }

        let x = node.position.x;
        let y = node.position.y;

        if (node.parentNode) {
            const parent = nodeMap.get(node.parentNode);
            if (parent) {
                const parentPosition = getAbsolutePosition(parent, nodeMap, absolutePositionCache);
                x += parentPosition.x;
                y += parentPosition.y;
            }
        }

        const absolutePosition = { x, y };
        absolutePositionCache.set(node.id, absolutePosition);

        return absolutePosition;
    };

    const buildSnapCandidateIndex = (graphId: string): SpatialBucketIndex<SnapCandidate> => {
        const index = new SpatialBucketIndex<SnapCandidate>();
        if (!connectionSource.value) {
            return index;
        }

        const { getNodes, getEdges } = useVueFlow('main-graph-' + graphId);
        const nodes = getNodes.value;
        const nodeMap = new Map(nodes.map((node) => [node.id, node]));
        const absolutePositionCache = new Map<string, { x: number; y: number }>();
        const sourceNode = nodeMap.get(connectionSource.value.nodeId);

        if (!sourceNode) {
            return index;
        }

        const sourceNodeId = connectionSource.value.nodeId;
        const sourceType = connectionSource.value.type;
        const targetType = sourceType === 'source' ? 'target' : 'source';
        const fixedTargetHandleId =
            sourceType === 'target' ? connectionSource.value.handleId : undefined;
        const occupiedTargetHandles =
            sourceType === 'source'
                ? new Set(getEdges.value.map((edge) => edge.targetHandle).filter(Boolean))
                : new Set<string>();
        for (const node of nodes) {
            if (node.id === sourceNodeId || !node.handleBounds) continue;

            const handles = node.handleBounds[targetType] as HandleElement[] | undefined;
            if (!handles?.length) continue;

            if (
                fixedTargetHandleId &&
                !isSourceNodeTypeCompatibleWithTargetHandle(node.type as string, fixedTargetHandleId)
            ) {
                continue;
            }

            const nodeAbsPos = getAbsolutePosition(node, nodeMap, absolutePositionCache);

            for (const handle of handles) {
                if (
                    sourceType === 'source' &&
                    !isSourceNodeTypeCompatibleWithTargetHandle(
                        sourceNode.type as string,
                        handle.id,
                    )
                ) {
                    continue;
                }

                if (sourceType === 'source') {
                    const handleCategory = getHandleCategory(handle.id);

                    if (
                        !acceptsMultipleInputEdges(handleCategory, node.type) &&
                        occupiedTargetHandles.has(handle.id)
                    ) {
                        continue;
                    }
                }

                const candidate: SnapCandidate = {
                    nodeId: node.id,
                    handleId: handle.id,
                    position: {
                        x: nodeAbsPos.x + handle.x + handle.width / 2,
                        y: nodeAbsPos.y + handle.y + handle.height / 2,
                    },
                    type: handle.type,
                };
                index.insert(
                    { ...candidate.position, width: 0, height: 0 },
                    candidate,
                );
            }
        }

        return index;
    };

    const updateNearestHandle = (mousePos: { x: number; y: number }, graphId: string) => {
        if (!connectionSource.value) {
            return;
        }

        if (snapCandidateIndex === null) {
            snapCandidateIndex = buildSnapCandidateIndex(graphId);
        }

        const closestHandle = snapCandidateIndex.findNearest(
            mousePos,
            (candidate) => candidate.position,
        );

        if (snappedHandle.value?.handleId !== closestHandle?.handleId) {
            snappedHandle.value = closestHandle;
        }
    };

    const findNearestHandle = (mousePos: { x: number; y: number }, graphId: string) => {
        if (!connectionSource.value) {
            return;
        }

        pendingMousePosition.value = mousePos;
        pendingGraphId.value = graphId;

        if (animationFrameId.value !== null) {
            return;
        }

        if (typeof window === 'undefined') {
            updateNearestHandle(mousePos, graphId);
            return;
        }

        animationFrameId.value = window.requestAnimationFrame(() => {
            const nextMousePosition = pendingMousePosition.value;
            const nextGraphId = pendingGraphId.value;

            animationFrameId.value = null;

            if (!nextMousePosition || !nextGraphId) {
                return;
            }

            updateNearestHandle(nextMousePosition, nextGraphId);
        });
    };

    return {
        snappedHandle,
        connectionSource,
        startSnapping,
        stopSnapping,
        findNearestHandle,
    };
};
