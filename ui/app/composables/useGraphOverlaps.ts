import { type GraphNode, type Rect } from '@vue-flow/core';

import {
    calculateOverlapTranslation,
    type OverlapResolutionDirection,
} from '@/utils/graphGeometry';
import { SpatialBucketIndex } from '@/utils/spatialIndex';
import type { ComputedRef, Ref } from 'vue';

export const AUTO_PLACEMENT_GAP = 150;

interface ResolveOverlapOptions {
    direction?: OverlapResolutionDirection;
    gap?: number;
    maxIterations?: number;
}

interface BlockerEntry {
    node: GraphNode;
    order: number;
    rect: Rect;
}

export const useGraphOverlaps = (graphIdOverride?: Ref<string> | ComputedRef<string>) => {
    const route = useRoute();
    const { error } = useToast();
    const { getBlockByNodeType } = useBlocks();

    const graphId = computed(() => graphIdOverride?.value ?? firstRouteString(route.params.id) ?? '');

    const nodeToRect = (node: GraphNode): Rect => {
        const minimumSize = getBlockByNodeType(nodeTypeOrUndefined(node.type))?.minSize;
        return {
            x: node.position.x,
            y: node.position.y,
            width:
                node.dimensions?.width ||
                (isRuntimeNumber(node.width) && node.width > 0
                    ? node.width
                    : (minimumSize?.width ?? 0)),
            height:
                node.dimensions?.height ||
                (isRuntimeNumber(node.height) && node.height > 0
                    ? node.height
                    : (minimumSize?.height ?? 0)),
        };
    };

    const resolveOverlaps = (
        nodeId: string | undefined,
        attachedNodeIds: (string | undefined)[],
        options?: ResolveOverlapOptions,
    ) => {
        const { findNode, updateNode, getNodes, isNodeIntersecting } = useGraphFlow(
            'main-graph-' + graphId.value,
        );

        const aOptions = {
            direction: options?.direction ?? 'right',
            gap: options?.gap ?? AUTO_PLACEMENT_GAP,
            maxIterations: options?.maxIterations ?? 50,
        };

        const mainNode = findNode(nodeId);
        if (!mainNode) {
            console.error(`[resolveOverlaps] Main node with ID ${nodeId} not found.`);
            error(`[resolveOverlaps] Main node with ID ${nodeId} not found.`, {
                title: 'Error',
            });
            return;
        }

        const movableNodes = [mainNode];
        const movableNodeIds = new Set([mainNode.id]);
        for (const attachedId of attachedNodeIds) {
            if (!attachedId || movableNodeIds.has(attachedId)) continue;
            const attachedNode = findNode(attachedId);
            if (attachedNode) {
                movableNodes.push(attachedNode);
                movableNodeIds.add(attachedId);
            } else {
                console.warn(`[resolveOverlaps] Attached node with ID ${attachedId} not found.`);
            }
        }

        const otherNodes = getNodes.value.filter(
            (node) => !movableNodeIds.has(node.id) && !node.id.startsWith('group-'),
        );
        if (otherNodes.length === 0) {
            return;
        }

        const blockerIndex = new SpatialBucketIndex<BlockerEntry>();
        otherNodes.forEach((node, order) => {
            const rect = nodeToRect(node);
            blockerIndex.insert(rect, { node, order, rect });
        });

        let iteration = 0;
        while (iteration < aOptions.maxIterations) {
            const movableNodeRects = movableNodes.map(nodeToRect);

            const candidateEntries = new Map<number, BlockerEntry>();
            for (const memberRect of movableNodeRects) {
                for (const candidate of blockerIndex.query(memberRect)) {
                    candidateEntries.set(candidate.order, candidate);
                }
            }

            const intersectingEntry = [...candidateEntries.values()]
                .sort((left, right) => left.order - right.order)
                .find((candidate) =>
                    movableNodeRects.some((memberRect) =>
                        isNodeIntersecting(memberRect, candidate.rect),
                    ),
                );

            if (!intersectingEntry) {
                return;
            }

            const delta = calculateOverlapTranslation(
                movableNodeRects,
                intersectingEntry.rect,
                aOptions.direction,
                aOptions.gap,
            );

            for (const movableNode of movableNodes) {
                movableNode.position.x += delta.x;
                movableNode.position.y += delta.y;
                updateNode(movableNode.id, { position: { ...movableNode.position } });
            }

            iteration++;
        }

        if (iteration >= aOptions.maxIterations) {
            console.warn(
                `[resolveOverlaps] Reached max iterations for node ${nodeId}. Could not resolve all overlaps.`,
            );
        }
    };

    return {
        resolveOverlaps,
    };
};
