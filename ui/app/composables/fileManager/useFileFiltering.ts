import type { BlockAttachmentSettings, FileManagerSort } from '@/types/settings';

const LAST_SORT_STORAGE_KEY = 'meridian-file-sort';
const LAST_VIEW_STORAGE_KEY = 'meridian-file-view-mode';

const DEFAULT_SORT: FileManagerSort = 'name_asc';
const DEFAULT_VIEW: ViewMode = 'grid';

const fileManagerSortValues = [
    'name_asc',
    'name_desc',
    'date_asc',
    'date_desc',
    'size_asc',
    'size_desc',
    'type_asc',
    'type_desc',
] as const satisfies readonly FileManagerSort[];

const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'avif'];
const textExtensions = [
    'txt',
    'md',
    'markdown',
    'csv',
    'json',
    'jsonl',
    'xml',
    'yaml',
    'yml',
    'log',
    'ts',
    'tsx',
    'js',
    'jsx',
    'vue',
    'py',
    'css',
    'html',
];

const sortConfig: Record<FileManagerSort, { sortBy: SortOption; sortDirection: SortDirection }> = {
    name_asc: { sortBy: 'name', sortDirection: 'asc' },
    name_desc: { sortBy: 'name', sortDirection: 'desc' },
    date_asc: { sortBy: 'date', sortDirection: 'asc' },
    date_desc: { sortBy: 'date', sortDirection: 'desc' },
    size_asc: { sortBy: 'size', sortDirection: 'asc' },
    size_desc: { sortBy: 'size', sortDirection: 'desc' },
    type_asc: { sortBy: 'type', sortDirection: 'asc' },
    type_desc: { sortBy: 'type', sortDirection: 'desc' },
};

const isFileManagerSort = (value: string | null | undefined): value is FileManagerSort => {
    return fileManagerSortValues.includes(value as FileManagerSort);
};

const isViewMode = (value: string | null | undefined): value is ViewMode => {
    return value === 'grid' || value === 'gallery' || value === 'list';
};

const getSortValue = (sortBy: SortOption, sortDirection: SortDirection): FileManagerSort => {
    return `${sortBy}_${sortDirection}` as FileManagerSort;
};

const getFileExtension = (item: FileSystemObject) => {
    return item.name.split('.').pop()?.toLowerCase() ?? '';
};

const getContentType = (item: FileSystemObject) => {
    return item.content_type?.split(';')[0].trim().toLowerCase() ?? '';
};

const isImageFile = (item: FileSystemObject) => {
    if (item.type !== 'file') return false;
    return getContentType(item).startsWith('image/') || imageExtensions.includes(getFileExtension(item));
};

const isPdfFile = (item: FileSystemObject) => {
    if (item.type !== 'file') return false;
    return getContentType(item) === 'application/pdf' || getFileExtension(item) === 'pdf';
};

const isTextFile = (item: FileSystemObject) => {
    if (item.type !== 'file') return false;
    return getContentType(item).startsWith('text/') || textExtensions.includes(getFileExtension(item));
};

const getTypeLabel = (item: FileSystemObject) => {
    if (item.type === 'folder') return 'folder';
    return getContentType(item) || getFileExtension(item) || 'file';
};

const matchesFileTypeFilter = (item: FileSystemObject, filter: FileTypeFilter) => {
    if (filter === 'all') return true;
    if (filter === 'folders') return item.type === 'folder';
    if (filter === 'images') return isImageFile(item);
    if (filter === 'pdfs') return isPdfFile(item);
    return isTextFile(item);
};

export const useFileFiltering = (
    items: Ref<FileSystemObject[]>,
    allUploadItems: Ref<FileSystemObject[]>,
    isUserUploadsTab: Ref<boolean>,
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
    const fileTypeFilter = ref<FileTypeFilter>('all');
    const foldersFirst = ref(true);
    const searchScope = ref<FileSearchScope>('current');
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
    const activeItems = computed(() => {
        if (isUserUploadsTab.value && searchScope.value === 'all_uploads') {
            return allUploadItems.value;
        }

        return items.value;
    });

    const filteredAndSortedItems = computed(() => {
        const normalizedSearch = searchQuery.value.trim().toLowerCase();

        const filtered = activeItems.value.filter((item) => {
            const matchesSearch =
                !normalizedSearch ||
                item.name.toLowerCase().includes(normalizedSearch) ||
                item.path?.toLowerCase().includes(normalizedSearch);

            return matchesSearch && matchesFileTypeFilter(item, fileTypeFilter.value);
        });

        return filtered.sort((a, b) => {
            if (foldersFirst.value) {
                if (a.type === 'folder' && b.type !== 'folder') return -1;
                if (a.type !== 'folder' && b.type === 'folder') return 1;
            }

            let comparison = 0;
            if (sortBy.value === 'name') {
                comparison = a.name.localeCompare(b.name, undefined, { numeric: true });
            } else if (sortBy.value === 'date') {
                comparison = a.updated_at.localeCompare(b.updated_at);
            } else if (sortBy.value === 'size') {
                comparison = (a.size ?? 0) - (b.size ?? 0);
            } else if (sortBy.value === 'type') {
                comparison = getTypeLabel(a).localeCompare(getTypeLabel(b));
            }

            if (comparison === 0) {
                comparison = a.name.localeCompare(b.name, undefined, { numeric: true });
            }

            return sortDirection.value === 'asc' ? comparison : -comparison;
        });
    });

    return {
        searchQuery,
        fileTypeFilter,
        foldersFirst,
        searchScope,
        sortBy,
        sortDirection,
        viewMode,
        toggleViewMode,
        activeItems,
        filteredAndSortedItems,
    };
};
