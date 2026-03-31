import { GRAPHS_PAGE_SIZE } from '@/constants';
import type { GraphSummary, Folder, Workspace } from '@/types/graph';

let fetchHistoryPromise: Promise<void> | null = null;
let fetchNextGraphsPagePromise: Promise<void> | null = null;

export const useHistoryData = () => {
    const { getGraphs, getHistoryFolders, getWorkspaces } = useAPI();
    const { error } = useToast();

    const graphs = useState<GraphSummary[]>('history-graphs', () => []);
    const folders = useState<Folder[]>('history-folders', () => []);
    const workspaces = useState<Workspace[]>('history-workspaces', () => []);
    const hasMoreGraphs = useState<boolean>('history-has-more-graphs', () => true);
    const nextGraphsOffset = useState<number>('history-next-graphs-offset', () => 0);
    const hasLoadedHistory = useState<boolean>('history-has-loaded', () => false);
    const isFetchingHistory = useState<boolean>('history-is-fetching', () => false);
    const isFetchingMoreGraphs = useState<boolean>('history-is-fetching-more', () => false);

    const fetchData = async (force: boolean = false) => {
        if (hasLoadedHistory.value && !force) return;
        if (fetchHistoryPromise) return await fetchHistoryPromise;

        fetchHistoryPromise = (async () => {
            isFetchingHistory.value = true;

            try {
                const [graphsPage, foldersData, workspacesData] = await Promise.all([
                    getGraphs(0, GRAPHS_PAGE_SIZE),
                    getHistoryFolders(),
                    getWorkspaces(),
                ]);

                graphs.value = graphsPage.items;
                folders.value = foldersData;
                workspaces.value = workspacesData;
                hasMoreGraphs.value = graphsPage.has_more;
                nextGraphsOffset.value = graphsPage.next_offset ?? graphsPage.items.length;
                hasLoadedHistory.value = true;
            } catch (err: unknown) {
                console.error('Error fetching history data:', err);
                error('Failed to load history.', { title: 'Load Error' });
                throw err;
            } finally {
                isFetchingHistory.value = false;
                fetchHistoryPromise = null;
            }
        })();

        return await fetchHistoryPromise;
    };

    const fetchNextGraphsPage = async () => {
        if (isFetchingMoreGraphs.value || !hasMoreGraphs.value) return;
        if (fetchNextGraphsPagePromise) return await fetchNextGraphsPagePromise;

        fetchNextGraphsPagePromise = (async () => {
            isFetchingMoreGraphs.value = true;

            try {
                const graphsPage = await getGraphs(nextGraphsOffset.value, GRAPHS_PAGE_SIZE);
                graphs.value = [...graphs.value, ...graphsPage.items];
                hasMoreGraphs.value = graphsPage.has_more;
                nextGraphsOffset.value =
                    graphsPage.next_offset ?? nextGraphsOffset.value + graphsPage.items.length;
            } catch (err: unknown) {
                console.error('Error fetching more graphs:', err);
                throw err;
            } finally {
                isFetchingMoreGraphs.value = false;
                fetchNextGraphsPagePromise = null;
            }
        })();

        return await fetchNextGraphsPagePromise;
    };

    return {
        graphs,
        folders,
        workspaces,
        hasMoreGraphs,
        hasLoadedHistory,
        isFetchingHistory,
        isFetchingMoreGraphs,
        fetchData,
        fetchNextGraphsPage,
    };
};
