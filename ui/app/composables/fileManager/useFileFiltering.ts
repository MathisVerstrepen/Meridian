export const useFileFiltering = (items: Ref<FileSystemObject[]>) => {
    // --- State ---
    const searchQuery = ref('');
    const sortBy = ref<SortOption>('name');
    const sortDirection = ref<SortDirection>('asc');
    const viewMode = ref<ViewMode>('grid');

    // --- Lifecycle ---
    onMounted(() => {
        const savedViewMode = localStorage.getItem('meridian-file-view-mode');
        if (savedViewMode === 'grid' || savedViewMode === 'list' || savedViewMode === 'gallery') {
            viewMode.value = savedViewMode as ViewMode;
        }
    });

    // --- Actions ---
    const toggleViewMode = (mode: ViewMode) => {
        viewMode.value = mode;
        localStorage.setItem('meridian-file-view-mode', mode);
    };

    // --- Computed ---
    const filteredAndSortedItems = computed(() => {
        // Filter
        const filtered = items.value.filter((item) =>
            item.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
        );

        // Sort
        return filtered.sort((a, b) => {
            if (a.type === 'folder' && b.type !== 'folder') return -1;
            if (a.type !== 'folder' && b.type === 'folder') return 1;

            let comparison = 0;
            if (sortBy.value === 'name') {
                comparison = a.name.localeCompare(b.name, undefined, { numeric: true });
            } else if (sortBy.value === 'date') {
                comparison = a.updated_at.localeCompare(b.updated_at);
            }

            return sortDirection.value === 'asc' ? comparison : -comparison;
        });
    });

    return {
        searchQuery,
        sortBy,
        sortDirection,
        viewMode,
        toggleViewMode,
        filteredAndSortedItems,
    };
};
