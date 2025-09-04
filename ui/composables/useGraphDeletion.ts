import type { Graph } from '@/types/graph';

export const useGraphDeletion = (
    graphs: Ref<Graph[]>,
    currentGraphId: Ref<string | undefined> | undefined,
) => {
    const { deleteGraph: apiDeleteGraph } = useAPI();
    const chatStore = useChatStore();
    const { resetChatState } = chatStore;
    const { lastOpenedChatId, openChatId } = storeToRefs(chatStore);
    const { success, error } = useToast();

    const handleDeleteGraph = async (
        graphId: string,
        graphName: string,
        navigateOnDelete: boolean,
    ) => {
        if (
            !confirm(`Are you sure you want to delete graph "${graphName}"? This cannot be undone.`)
        ) {
            return;
        }

        const originalGraphs = [...graphs.value];
        const graphIndex = graphs.value.findIndex((g) => g.id === graphId);

        // Optimistically remove from the UI
        if (graphIndex !== -1) {
            graphs.value.splice(graphIndex, 1);
        }

        try {
            await apiDeleteGraph(graphId);
            success('Graph deleted successfully.', { title: 'Graph Deleted' });

            // Handle navigation if the current graph was deleted
            if (currentGraphId && currentGraphId.value === graphId) {
                resetChatState();
                lastOpenedChatId.value = null;
                openChatId.value = null;

                if (!navigateOnDelete) {
                    return;
                }

                // Navigate to the next graph or home if none left
                const nextGraph = graphs.value[0];
                if (nextGraph) {
                    await navigateTo(`/graph/${nextGraph.id}`);
                } else {
                    await navigateTo('/');
                }
            }
        } catch (err) {
            console.error('Error deleting graph:', err);
            error('Failed to delete graph. Please try again.', { title: 'Deletion Error' });
            // Revert on failure
            graphs.value = originalGraphs;
        }
    };

    return {
        handleDeleteGraph,
    };
};
