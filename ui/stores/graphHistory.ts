import type { Graph } from '@/types/graph';

export const useGraphHistoryStore = defineStore('graphHistory', () => {
    const graphs = ref<Graph[]>([]);
    const hasFetched = ref(false);
    const error = ref<Error | null>(null);

    async function fetchGraphsIfNeeded() {
        if (hasFetched.value) {
            return;
        }

        error.value = null;
        const { getGraphs } = useAPI();

        try {
            const response = await getGraphs();
            graphs.value = response;
            hasFetched.value = true;
        } catch (err) {
            console.error('Error fetching graphs:', err);
            error.value = err instanceof Error ? err : new Error('Failed to fetch graphs');
            hasFetched.value = false;
        }
    }

    async function addGraph() {
        error.value = null;
        const { createGraph } = useAPI();

        try {
            const newGraph = await createGraph();
            graphs.value.push(newGraph);
            return newGraph;
        } catch (err) {
            console.error('Error creating graph:', err);
            error.value = err instanceof Error ? err : new Error('Failed to create graph');
            throw err;
        }
    }

    function clearHistory() {
        graphs.value = [];
        hasFetched.value = false;
    }


    return {
        graphs,
        hasFetched,
        error,
        fetchGraphsIfNeeded,
        addGraph,
        clearHistory,
    };
});