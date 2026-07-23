import type { GraphNode, Connection, GraphEdge } from '@vue-flow/core';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';

const acceptedMapping: Record<string, string[]> = {
    prompt: ['prompt'],
    context: ['textToText', 'parallelization', 'routing', 'contextMerger'],
    attachment: ['filePrompt', 'github'],
};

export const isSourceNodeTypeCompatibleWithTargetHandle = (
    sourceNodeType?: string,
    targetHandleId?: string | null,
) => {
    const targetType = targetHandleId?.split('_')[0];

    if (!sourceNodeType || !targetType) {
        return false;
    }

    return acceptedMapping[targetType]?.includes(sourceNodeType) ?? false;
};

export const isDuplicateConnection = (existingEdges: GraphEdge[], candidate: Connection): boolean =>
    existingEdges.some(
        (edge) =>
            edge.source === candidate.source &&
            edge.sourceHandle === candidate.sourceHandle &&
            edge.target === candidate.target &&
            edge.targetHandle === candidate.targetHandle,
    );

export const useEdgeCompatibility = () => {
    const { warning } = useToast();

    const acceptMultipleInputEdges: Record<NodeCategoryEnum, boolean> = {
        [NodeCategoryEnum.PROMPT]: false,
        [NodeCategoryEnum.CONTEXT]: false,
        [NodeCategoryEnum.ATTACHMENT]: true,
    };

    const acceptsMultipleInputEdges = (
        handleCategory: string,
        targetNodeType?: string,
        explicitMultiple = false,
    ): boolean =>
        acceptMultipleInputEdges[handleCategory as NodeCategoryEnum] ||
        explicitMultiple ||
        (handleCategory === NodeCategoryEnum.CONTEXT &&
            targetNodeType === NodeTypeEnum.CONTEXT_MERGER);

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

        if (isSourceNodeTypeCompatibleWithTargetHandle(sourceNode.type, connection.targetHandle)) {
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
        multiple = false,
    ): boolean => {
        if (handleType !== 'target') return true;

        if (acceptsMultipleInputEdges(handleCategory, node.type, multiple)) return true;

        const handleId = `${handleCategory}_${node.id}`;
        return !connectedEdges.some((edge) => edge.targetHandle === handleId);
    };

    return {
        checkEdgeCompatibility,
        handleConnectableInput,
        acceptMultipleInputEdges,
        acceptsMultipleInputEdges,
    };
};
