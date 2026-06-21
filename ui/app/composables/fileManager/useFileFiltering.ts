import type { BlockAttachmentSettings, FileManagerSort } from '@/types/settings';

const LAST_SORT_STORAGE_KEY = 'meridian-file-sort';
const LAST_VIEW_STORAGE_KEY = 'meridian-file-view-mode';

const DEFAULT_SORT: FileManagerSort = 'name_asc';
const DEFAULT_VIEW: ViewMode = 'grid';

const sortConfig: Record<FileManagerSort, { sortBy: SortOption; sortDirection: SortDirection }> = {
    name_asc: { sortBy: 'name', sortDirection: 'asc' },
    name_desc: { sortBy: 'name', sortDirection: 'desc' },
    date_asc: { sortBy: 'date', sortDirection: 'asc' },
    date_desc: { sortBy: 'date', sortDirection: 'desc' },
};

const isFileManagerSort = (value: string | null | undefined): value is FileManagerSort => {
    return value === 'name_asc' || value === 'name_desc' || value === 'date_asc' || value === 'date_desc';
};

const isViewMode = (value: string | null | undefined): value is ViewMode => {
    return value === 'grid' || value === 'gallery' || value === 'list';
};

const getSortValue = (sortBy: SortOption, sortDirection: SortDirection): FileManagerSort => {
    return `${sortBy}_${sortDirection}` as FileManagerSort;
};

export const useFileFiltering = (
    items: Ref<FileSystemObject[]>,
    blockAttachmentSettings: Ref<BlockAttachmentSettings>,
) => {
    const getDefaultSort = () => {
        return isFileManagerSort(blockAttachmentSettings.value.file_manager_default_sort)
            ? blockAttachmentSettings.value.file_manager_default_sort
            : DEFAULT_SORT;
    };

    const getDefaultView = () => {
        return isViewMode(blockAttachmentSettings.value.file_manager_default_view)
            ? blockAttachmentSettings.value.file_manager_default_view
            : DEFAULT_VIEW;
    };

    const getInitialSort = () => {
        if (import.meta.client && blockAttachmentSettings.value.file_manager_remember_last_sort) {
            const savedSort = localStorage.getItem(LAST_SORT_STORAGE_KEY);
            if (isFileManagerSort(savedSort)) return savedSort;
        }

        return getDefaultSort();
    };

    const getInitialView = () => {
        if (import.meta.client && blockAttachmentSettings.value.file_manager_remember_last_view) {
            const savedViewMode = localStorage.getItem(LAST_VIEW_STORAGE_KEY);
            if (isViewMode(savedViewMode)) return savedViewMode;
        }

        return getDefaultView();
    };

    const initialSort = sortConfig[getInitialSort()];

    // --- State ---
    const searchQuery = ref('');
    const sortBy = ref<SortOption>(initialSort.sortBy);
    const sortDirection = ref<SortDirection>(initialSort.sortDirection);
    const viewMode = ref<ViewMode>(getInitialView());
    const isApplyingSortPreference = ref(false);

    const applySortPreference = (sort: FileManagerSort) => {
        isApplyingSortPreference.value = true;
        sortBy.value = sortConfig[sort].sortBy;
        sortDirection.value = sortConfig[sort].sortDirection;
        void nextTick(() => {
            isApplyingSortPreference.value = false;
        });
    };

    // --- Actions ---
    const toggleViewMode = (mode: ViewMode) => {
        viewMode.value = mode;
        if (import.meta.client && blockAttachmentSettings.value.file_manager_remember_last_view) {
            localStorage.setItem(LAST_VIEW_STORAGE_KEY, mode);
        }
    };

    // --- Watchers ---
    watch(
        () => [
            blockAttachmentSettings.value.file_manager_default_sort,
            blockAttachmentSettings.value.file_manager_remember_last_sort,
        ],
        () => {
            if (import.meta.client && blockAttachmentSettings.value.file_manager_remember_last_sort) {
                const savedSort = localStorage.getItem(LAST_SORT_STORAGE_KEY);
                applySortPreference(isFileManagerSort(savedSort) ? savedSort : getDefaultSort());
                return;
            }

            applySortPreference(getDefaultSort());
        },
    );

    watch([sortBy, sortDirection], () => {
        if (
            !import.meta.client ||
            isApplyingSortPreference.value ||
            !blockAttachmentSettings.value.file_manager_remember_last_sort
        ) {
            return;
        }

        localStorage.setItem(LAST_SORT_STORAGE_KEY, getSortValue(sortBy.value, sortDirection.value));
    });

    watch(
        () => [
            blockAttachmentSettings.value.file_manager_default_view,
            blockAttachmentSettings.value.file_manager_remember_last_view,
        ],
        () => {
            if (import.meta.client && blockAttachmentSettings.value.file_manager_remember_last_view) {
                const savedViewMode = localStorage.getItem(LAST_VIEW_STORAGE_KEY);
                viewMode.value = isViewMode(savedViewMode) ? savedViewMode : getDefaultView();
                return;
            }

            viewMode.value = getDefaultView();
        },
    );

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
