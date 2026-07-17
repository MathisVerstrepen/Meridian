import { useVueFlow, type Rect } from '@vue-flow/core';

import type { NodeTypeEnum } from '@/types/enums';
import type { NodeWithDimensions } from '@/types/graph';
import type { ComputedRef, Ref } from 'vue';

export const AUTO_PLACEMENT_GAP = 150;

type OverlapResolutionDirection = 'right' | 'below';

interface ResolveOverlapOptions {
    direction?: OverlapResolutionDirection;
    gap?: number;
    maxIterations?: number;
}

export const useGraphOverlaps = (graphIdOverride?: Ref<string> | ComputedRef<string>) => {
    const route = useRoute();
    const { error } = useToast();
    const { getBlockByNodeType } = useBlocks();

    const graphId = computed(() => graphIdOverride?.value ?? (route.params.id as string));

    const nodeToRect = (node: NodeWithDimensions): Rect => {
        const minimumSize = getBlockByNodeType(node.type as NodeTypeEnum)?.minSize;
        return {
            x: node.position.x,
            y: node.position.y,
            width:
                node.dimensions?.width ||
                (typeof node.width === 'number' && node.width > 0
                    ? node.width
                    : (minimumSize?.width ?? 0)),
            height:
                node.dimensions?.height ||
                (typeof node.height === 'number' && node.height > 0
                    ? node.height
                    : (minimumSize?.height ?? 0)),
        };
    };

    const resolveOverlaps = (
        nodeId: string | undefined,
        attachedNodeIds: (string | undefined)[],
        options?: ResolveOverlapOptions,
    ) => {
        const { findNode, updateNode, getNodes, isNodeIntersecting } = useVueFlow(
            'main-graph-' + graphId.value,
        );

        const aOptions = {
            direction: 'right' as OverlapResolutionDirection,
            gap: AUTO_PLACEMENT_GAP,
            maxIterations: 50,
            ...options,
        };

        const mainNode = findNode(nodeId) as NodeWithDimensions | undefined;
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
            const attachedNode = findNode(attachedId) as NodeWithDimensions | undefined;
            if (attachedNode) {
                movableNodes.push(attachedNode);
                movableNodeIds.add(attachedId);
            } else {
                console.warn(`[resolveOverlaps] Attached node with ID ${attachedId} not found.`);
            }
        }

        const otherNodes = getNodes.value.filter(
            (node) => !movableNodeIds.has(node.id) && !node.id.startsWith('group-'),
        ) as NodeWithDimensions[];
        if (otherNodes.length === 0) {
            return;
        }

        let iteration = 0;
        while (iteration < aOptions.maxIterations) {
            const movableNodeRects = movableNodes.map(nodeToRect);

            const intersectingNode = otherNodes.find((otherNode) => {
                const otherNodeRect = nodeToRect(otherNode);
                return movableNodeRects.some((memberRect) =>
                    isNodeIntersecting(memberRect, otherNodeRect),
                );
            });

            if (!intersectingNode) {
                return;
            }

            const intersectingNodeRect = nodeToRect(intersectingNode);
            const groupBounds = movableNodeRects.reduce((bounds, memberRect) => {
                const right = Math.max(bounds.x + bounds.width, memberRect.x + memberRect.width);
                const bottom = Math.max(
                    bounds.y + bounds.height,
                    memberRect.y + memberRect.height,
                );
                const x = Math.min(bounds.x, memberRect.x);
                const y = Math.min(bounds.y, memberRect.y);
                return { x, y, width: right - x, height: bottom - y };
            });
            const delta =
                aOptions.direction === 'below'
                    ? {
                          x: 0,
                          y:
                              intersectingNodeRect.y +
                              intersectingNodeRect.height +
                              aOptions.gap -
                              groupBounds.y,
                      }
                    : {
                          x:
                              intersectingNodeRect.x +
                              intersectingNodeRect.width +
                              aOptions.gap -
                              groupBounds.x,
                          y: 0,
                      };

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
