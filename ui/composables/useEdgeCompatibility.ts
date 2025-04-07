import {
    type GraphNode,
    type Connection,
    type HandleConnectableFunc,
} from '@vue-flow/core';

const acceptedMapping: Record<string, string[]> = {
    prompt: ['prompt'],
    context: ['textToText'],
};

export const useEdgeCompatibility = () => {
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
        let sourceNode = getNodes.value.find(
            (node) => node.id === connection.source,
        );
        let targetType = connection.targetHandle?.split('_')[0];

        if (!sourceNode || !targetType) {
            return false;
        }

        return acceptedMapping[targetType]?.includes(sourceNode.type);
    };

    const handleConnectableInputContext: HandleConnectableFunc = (
        node,
        connectedEdges,
    ) => {
        for (const edge of connectedEdges) {
            if (edge.targetHandle === 'context_' + node.id) {
                return false;
            }
        }
        return true;
    };

    const handleConnectableInputPrompt: HandleConnectableFunc = (
        node,
        connectedEdges,
    ) => {
        for (const edge of connectedEdges) {
            if (edge.targetHandle === 'prompt_' + node.id) {
                return false;
            }
        }
        return true;
    };

    return {
        checkEdgeCompatibility,
        handleConnectableInputContext,
        handleConnectableInputPrompt,
    };
};
