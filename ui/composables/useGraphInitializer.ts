import type { Node, Edge } from "@vue-flow/core";

// --- Configuration for Initial Nodes ---
const initialNodeDefinitions: Node[] = [
    {
        id: "1",
        type: "prompt",
        data: { prompt: "What is a LLM ? Short Answer" },
        position: { x: 700, y: 200 },
    },
    {
        id: "2",
        type: "textToText",
        data: { model: "google/gemini-2.0-flash-001" },
        position: { x: 800, y: 500 },
    },
];

const initialEdgeDefinitions: Edge[] = [
    {
        id: "e1-2",
        source: "1",
        target: "2",
    },
];

/**
 * Composable function that initializes a graph with nodes and edges.
 *
 * @param graphContainerRef - A Vue ref containing the HTML element that will host the graph
 * @returns An object containing reactive arrays of nodes and edges for the graph
 *
 * @remarks
 * The function positions the nodes relative to the center of the container element.
 * It uses `initialNodeDefinitions` to create the nodes (assumed to be defined elsewhere).
 * The graph is initialized after the component is mounted to ensure the DOM is ready.
 *
 * @example
 * ```ts
 * const graphRef = ref<HTMLElement | null>(null);
 * const { nodes, edges } = useGraphInitializer(graphRef);
 * ```
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

        nodes.value = initialNodeDefinitions;
        edges.value = initialEdgeDefinitions;
    };

    onMounted(() => {
        nextTick(initializeGraph);
    });

    return {
        nodes,
        edges,
    };
}
