import type { GraphNode, Connection, GraphEdge } from '@vue-flow/core';
import { NodeCategoryEnum } from '@/types/enums';

const acceptedMapping: Record<string, string[]> = {
    prompt: ['prompt'],
    context: ['textToText', 'parallelization', 'routing'],
    attachment: ['filePrompt', 'github'],
};

export const useEdgeCompatibility = () => {
    const { warning } = useToast();

    const acceptMultipleInputEdges: Record<NodeCategoryEnum, boolean> = {
        [NodeCategoryEnum.PROMPT]: false,
        [NodeCategoryEnum.CONTEXT]: false,
        [NodeCategoryEnum.ATTACHMENT]: true,
    };

    /**
     * Checks if a connection between two nodes is compatible based on node types.
     *
     * @param connection - The connection object containing source node ID and target handle information
     * @param getNodes - Computed reference to an array of all graph nodes
     * @returns Boolean indicating whether the connection is compatible (true) or not (false)
     *
     * The function works by:
     * 1. Finding the source node from the nodes array using the connection's source ID
     * 2. Extracting the target type from the connection's targetHandle
     * 3. Checking if the source node's type is included in the list of accepted types for the target type
     */
    const checkEdgeCompatibility = (
        connection: Connection,
        getNodes: GraphNode[],
        showWarning = true,
    ): boolean => {
        const sourceNode = getNodes.find((node) => node.id === connection.source);
        const targetType = connection.targetHandle?.split('_')[0];

        if (!sourceNode || !targetType) {
            if (showWarning) warning('Invalid connection: source node or target type is missing.');
            return false;
        }

        if (connection.targetHandle?.split('_')[1] === connection.sourceHandle?.split('_')[1]) {
            if (showWarning)
                warning(
                    'Invalid connection: source and target handles cannot be from the same node.',
                );
            return false;
        }

        if (acceptedMapping[targetType]?.includes(sourceNode.type)) {
            return true;
        }

        if (showWarning) warning('Invalid connection: incompatible node types.');
        return false;
    };

    const handleConnectableInput = (
        node: GraphNode,
        connectedEdges: GraphEdge[],
        handleCategory: string,
        handleType: 'source' | 'target',
    ): boolean => {
        if (handleType !== 'target') return true;

        const isMultipleAccepted = acceptMultipleInputEdges[handleCategory as NodeCategoryEnum];
        if (isMultipleAccepted) return true;

        const handleId = `${handleCategory}_${node.id}`;
        return !connectedEdges.some((edge) => edge.targetHandle === handleId);
    };

    return {
        checkEdgeCompatibility,
        handleConnectableInput,
        acceptMultipleInputEdges,
    };
};
