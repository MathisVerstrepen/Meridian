import type { Node, Edge } from "@vue-flow/core";

/**
 * Composable function that initializes a graph with nodes and edges in a given container.
 * 
 * @param graphContainerRef - Vue ref pointing to the HTML element that will contain the graph
 * @returns An object containing reactive arrays of nodes and edges
 * 
 * @example
 * ```ts
 * const graphContainer = ref<HTMLElement | null>(null)
 * const { nodes, edges } = useGraphInitializer(graphContainer)
 * ```
 * 
 * The graph is initialized on component mount using predefined node and edge definitions.
 * If the container reference is not available during initialization, a warning will be logged.
 */
export function useGraphInitializer(
    graphContainerRef: Ref<HTMLElement | null>
) {
    const nodes = ref<Node[]>([]);
    const edges = ref<Edge[]>([]);

    const initializeGraph = () => {
        const graphEl = graphContainerRef.value;
        if (!graphEl) {
            console.warn(
                "Graph container ref not yet available for initialization."
            );
            return;
        }
    };

    onMounted(() => {
        nextTick(initializeGraph);
    });

    return {
        nodes,
        edges,
    };
}
