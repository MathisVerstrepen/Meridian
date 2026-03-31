import type { GraphSummary, Folder } from '@/types/graph';

export const useSidebarData = () => {
    const {
        graphs,
        folders,
        workspaces,
        hasMoreGraphs,
        isFetchingMoreGraphs,
        fetchData,
        fetchNextGraphsPage,
    } = useHistoryData();

    // --- State ---
    const searchQuery = ref('');
    const searchScope = ref<'workspace' | 'global'>('workspace');
    const searchWorkspaceId = ref<string | null>(null);
    const expandedFolders = ref<Set<string>>(new Set());

    // --- Local Storage Keys ---
    const STORAGE_KEY = 'meridian_expanded_folders';

    const toggleFolder = (folderId: string) => {
        if (expandedFolders.value.has(folderId)) {
            expandedFolders.value.delete(folderId);
        } else {
            expandedFolders.value.add(folderId);
        }
    };

    // --- Computed ---
    const searchResults = computed(() => {
        if (!searchQuery.value) return [];

        let filteredGraphs = graphs.value;

        // Apply Scope Filtering
        if (searchScope.value === 'workspace' && searchWorkspaceId.value) {
            filteredGraphs = filteredGraphs.filter(
                (g) => g.workspace_id === searchWorkspaceId.value,
            );
        }

        return filteredGraphs
            .filter((graph) => graph.name.toLowerCase().includes(searchQuery.value.toLowerCase()))
            .sort((a, b) => Number(b.pinned) - Number(a.pinned));
    });

    const getOrganizedData = (
        activeWorkspaceId: string | null,
        currentGraphs: GraphSummary[],
        currentFolders: Folder[],
    ) => {
        if (searchQuery.value) return null;
        if (!activeWorkspaceId) return null;

        const wsFolders = currentFolders.filter((f) => f.workspace_id === activeWorkspaceId);
        const wsGraphs = currentGraphs.filter((g) => g.workspace_id === activeWorkspaceId);

        const pinned = wsGraphs.filter((g) => g.pinned);
        const unpinned = wsGraphs.filter((g) => !g.pinned);

        const folderMap = wsFolders
            .map((folder) => ({
                ...folder,
                graphs: currentGraphs
                    .filter((g) => g.folder_id === folder.id)
                    .sort(
                        (a, b) =>
                            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
                    ),
            }))
            .sort((a, b) => a.name.localeCompare(b.name));

        const loose = unpinned
            .filter((g) => !g.folder_id)
            .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

        return {
            pinned,
            folders: folderMap,
            loose,
        };
    };

    // --- Watchers ---
    watch(
        expandedFolders,
        (newFolders) => {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(newFolders)));
            } catch (e) {
                console.error('Failed to save expanded folders to localStorage', e);
            }
        },
        { deep: true },
    );

    // --- Init ---
    const initExpandedFolders = () => {
        try {
            const storedFolders = localStorage.getItem(STORAGE_KEY);
            if (storedFolders) {
                const parsedFolders = JSON.parse(storedFolders);
                if (Array.isArray(parsedFolders)) {
                    expandedFolders.value = new Set(parsedFolders);
                }
            }
        } catch (e) {
            console.error('Failed to load expanded folders from localStorage', e);
            localStorage.removeItem(STORAGE_KEY);
        }
    };

    return {
        graphs,
        folders,
        workspaces,
        searchQuery,
        searchScope,
        searchWorkspaceId,
        searchResults,
        expandedFolders,
        hasMoreGraphs,
        isFetchingMoreGraphs,
        fetchData,
        fetchNextGraphsPage,
        toggleFolder,
        getOrganizedData,
        initExpandedFolders,
    };
};
