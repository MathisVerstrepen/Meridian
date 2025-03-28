import type { Node, Edge } from "@vue-flow/core";

interface InitialNodeConfig {
    id: string;
    type: string;
    data: Record<string, any>;
    relativePos?: { x?: number; y?: number };
}

// --- Configuration for Initial Nodes ---
const initialNodeDefinitions: InitialNodeConfig[] = [
    {
        id: "1",
        type: "prompt",
        data: { prompt: "What is a LLM ? Short Answer" },
        relativePos: { y: -100 },
    },
    {
        id: "2",
        type: "textToText",
        data: { model: "google/gemini-2.0-flash-001" },
        relativePos: { y: 100 },
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

        const rect = graphEl.getBoundingClientRect();
        const nodeCenterOffsetX = 160;
        const nodeCenterOffsetY = 50;
        const centerX = Math.round(rect.width / 2 - nodeCenterOffsetX);
        const centerY = Math.round(rect.height / 2 - nodeCenterOffsetY);

        const initialNodes: Node[] = initialNodeDefinitions.map((config) => ({
            id: config.id,
            type: config.type,
            position: {
                x: centerX + (config.relativePos?.x ?? 0),
                y: centerY + (config.relativePos?.y ?? 0),
            },
            data: { ...config.data },
            label: config.type,
        }));

        nodes.value = initialNodes;
        edges.value = [];
    };

    onMounted(() => {
        nextTick(initializeGraph);
    });

    return {
        nodes,
        edges,
    };
}
