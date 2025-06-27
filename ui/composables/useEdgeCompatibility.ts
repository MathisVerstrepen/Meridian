import { type GraphNode, type Connection, type HandleConnectableFunc } from '@vue-flow/core';

const acceptedMapping: Record<string, string[]> = {
    prompt: ['prompt'],
    context: ['textToText', 'parallelization'],
    attachment: ['filePrompt'],
};

export const useEdgeCompatibility = () => {
    const { warning } = useToast();

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
        getNodes: globalThis.ComputedRef<GraphNode<any, any, string>[]>,
    ): Boolean => {
        let sourceNode = getNodes.value.find((node) => node.id === connection.source);
        let targetType = connection.targetHandle?.split('_')[1];

        if (!sourceNode || !targetType) {
            warning('Invalid connection: source node or target type is missing.');
            return false;
        }

        if (connection.targetHandle?.split('_')[2] === connection.sourceHandle?.split('_')[2]) {
            warning('Invalid connection: source and target handles cannot be from the same node.');
            return false;
        }

        if (acceptedMapping[targetType]?.includes(sourceNode.type)) {
            return true;
        }

        warning('Invalid connection: incompatible node types.');
        return false;
    };

    const handleConnectableInputContext: HandleConnectableFunc = (node, connectedEdges) => {
        for (const edge of connectedEdges) {
            if (edge.targetHandle === 'target_context_' + node.id) {
                return false;
            }
        }
        return true;
    };

    const handleConnectableInputPrompt: HandleConnectableFunc = (node, connectedEdges) => {
        for (const edge of connectedEdges) {
            if (edge.targetHandle === 'target_prompt_' + node.id) {
                return false;
            }
        }
        return true;
    };

    const handleConnectableInputAttachment: HandleConnectableFunc = (node, connectedEdges) => {
        for (const edge of connectedEdges) {
            if (edge.targetHandle === 'target_attachment_' + node.id) {
                return false;
            }
        }
        return true;
    };

    return {
        checkEdgeCompatibility,
        handleConnectableInputContext,
        handleConnectableInputPrompt,
        handleConnectableInputAttachment,
    };
};
