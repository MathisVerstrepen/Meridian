import { useVueFlow } from '@vue-flow/core';
import type { Node, Rect } from '@vue-flow/core';

type NodeWithDimensions = Node & {
    dimensions: {
        width: number;
        height: number;
    };
};

export const useGraphOverlaps = () => {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const nodeToRect = (node: NodeWithDimensions): Rect => {
        return {
            x: node.position.x,
            y: node.position.y,
            width: node.dimensions.width,
            height: node.dimensions.height,
        };
    };

    const resolveOverlaps = (
        nodeId: string,
        attachedNodeIds: string[],
        options?: { offsetX?: number; offsetY?: number; maxIterations?: number },
    ) => {
        const { findNode, updateNode, getNodes, isNodeIntersecting } = useVueFlow(
            'main-graph-' + graphId.value,
        );

        const aOptions = {
            offsetX: 700,
            offsetY: 0,
            maxIterations: 50,
            ...options,
        };

        const mainNode = findNode(nodeId) as NodeWithDimensions | undefined;
        if (!mainNode) {
            console.error(`[resolveOverlaps] Main node with ID ${nodeId} not found.`);
            return;
        }

        const otherNodes = getNodes.value.filter((n) => n.id !== nodeId) as NodeWithDimensions[];
        if (otherNodes.length === 0) {
            return;
        }

        let iteration = 0;
        while (iteration < aOptions.maxIterations) {
            const mainNodeRect = nodeToRect(mainNode);

            const intersectingNode = otherNodes.find((otherNode) =>
                isNodeIntersecting(mainNodeRect, nodeToRect(otherNode)),
            );

            if (!intersectingNode) {
                return;
            }

            // Move the main node
            mainNode.position.x += aOptions.offsetX;
            mainNode.position.y += aOptions.offsetY;

            const nodesToUpdate = [
                { id: mainNode.id, changes: { position: { ...mainNode.position } } },
            ];

            // Move all attached nodes
            for (const attachedId of attachedNodeIds) {
                const attachedNode = findNode(attachedId);
                if (attachedNode) {
                    attachedNode.position.x += aOptions.offsetX;
                    attachedNode.position.y += aOptions.offsetY;
                    nodesToUpdate.push({
                        id: attachedId,
                        changes: { position: { ...attachedNode.position } },
                    });
                } else {
                    console.warn(
                        `[resolveOverlaps] Attached node with ID ${attachedId} not found.`,
                    );
                }
            }

            nodesToUpdate.forEach((update) => updateNode(update.id, update.changes));

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
