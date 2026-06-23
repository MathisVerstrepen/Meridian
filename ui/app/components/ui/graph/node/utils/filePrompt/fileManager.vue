<script lang="ts" setup>
// --- Props & Emits ---
const props = defineProps<{
    initialSelectedFiles?: FileSystemObject[];
}>();
const emit = defineEmits(['close']);

// --- Stores ---
const settingsStore = useSettingsStore();
const { blockAttachmentSettings } = storeToRefs(settingsStore);

// --- Composables ---
const {
    activeTab,
    currentFolder,
    items,
    allUploadItems,
    breadcrumbs,
    canGoBack,
    canGoForward,
    isLoading,
    isAllUploadsLoading,
    imagePreviews,
    recentFolders,
    pinnedFolders,
    activeGoogleDriveSection,
    isUserUploadsTab,
    isGoogleDriveTab,
    isGoogleDriveConnected,
    googleDriveEmail,
    switchTab,
    switchGoogleDriveSection,
    handleNavigate,
    handleShortcutNavigate,
    goBack,
    goForward,
    loadAllUploads,
    invalidateAllUploads,
    togglePinnedFolder,
    initialize,
    loadImagePreviews,
    searchGoogleDrive,
} = useFileBrowser();

const {
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
} = useFileFiltering(items, allUploadItems, isUserUploadsTab, blockAttachmentSettings);

const isAllUploadsSearchMode = computed(
    () => isUserUploadsTab.value && searchScope.value === 'all_uploads',
);
const isContentLoading = computed(
    () => isLoading.value || (isAllUploadsSearchMode.value && isAllUploadsLoading.value),
);
const hasActiveFilters = computed(
    () => searchQuery.value.trim() !== '' || fileTypeFilter.value !== 'all',
);

const refreshAllUploadsIfNeeded = async () => {
    if (!isAllUploadsSearchMode.value) {
        invalidateAllUploads();
        return;
    }

    await loadAllUploads(viewMode.value, { force: true });
};

watch(viewMode, (newMode) => {
    loadImagePreviews(activeItems.value, newMode);
});

watch([searchScope, activeTab], () => {
    if (isAllUploadsSearchMode.value) {
        void loadAllUploads(viewMode.value);
    }
});

let googleDriveSearchTimeout: number | null = null;
watch(searchQuery, (query) => {
    if (!isGoogleDriveTab.value) return;
    if (googleDriveSearchTimeout) window.clearTimeout(googleDriveSearchTimeout);
    googleDriveSearchTimeout = window.setTimeout(() => {
        void searchGoogleDrive(query, viewMode.value);
    }, 300);
});

const {
    selectedFiles,
    handleSelect,
    handleRangeSelect,
    handleSelectFolderContents,
    selectItems,
    replaceVisibleSelection,
    clearSelection,
    isSelected,
    hasSelectedDescendants,
    isFolderFullySelected,
} = useFileSelection(props.initialSelectedFiles);

const {
    isCreatingFolder,
    newFolderName,
    isRenaming,
    renameInput,
    isDraggingOver,
    conflictRequest,
    isStorageFull,
    isUploading,
    uploadStatus,
    uploadTotalFiles,
    uploadCompletedFiles,
    uploadFailedFiles,
    currentFileName,
    currentFileProgress,
    uploadErrors,
    resolveConflictPolicy,
    cancelConflictPolicy,
    resetUploadState,
    handleCreateFolder,
    handleFileUploadFromEvent,
    handleDeleteItem,
    handleDeleteItems,
    submitRename,
    handleDownload,
    handleDownloadItems,
    handleMoveItems,
    handleCopyItems,
    startRename,
} = useFileOperations(
    items,
    currentFolder,
    isUserUploadsTab,
    (files) => loadImagePreviews(files, viewMode.value),
    refreshAllUploadsIfNeeded,
);

// --- Local State for Context Menu ---
const showContextMenu = ref(false);
const contextMenuPos = ref({ x: 0, y: 0 });
const contextMenuItem = ref<FileSystemObject | null>(null);
const uploadInputRef = ref<HTMLInputElement | null>(null);
const uploadFolderInputRef = ref<HTMLInputElement | null>(null);
const toolbarRef = ref<{ focusSearchInput: () => void } | null>(null);
const contentAreaRef = ref<HTMLElement | null>(null);
const pendingFileAction = ref<'move' | 'copy' | null>(null);
const pendingFileActionItems = ref<FileSystemObject[]>([]);

const canMoveFileManagerItem = (item: FileSystemObject) => {
    return isUserUploadsTab.value && !item.path?.startsWith('/Generated Images/');
};

const selectedItems = computed(() => Array.from(selectedFiles));
const selectedDownloadItems = computed(() => selectedItems.value.filter((item) => item.type === 'file'));
const selectedMovableItems = computed(() => selectedItems.value.filter(canMoveFileManagerItem));
const visibleSelectableItems = computed(() =>
    filteredAndSortedItems.value.filter((item) => item.type === 'file'),
);
const selectedVisibleCount = computed(
    () => visibleSelectableItems.value.filter((item) => isSelected(item)).length,
);
const selectedGroups = computed(() => {
    const groups = new Map<string, FileSystemObject[]>();

    selectedItems.value.forEach((item) => {
        const folderLabel = getSelectionFolderLabel(item);
        groups.set(folderLabel, [...(groups.get(folderLabel) ?? []), item]);
    });

    return Array.from(groups.entries()).map(([folder, groupItems]) => ({
        folder,
        totalCount: groupItems.length,
        items: groupItems.slice(0, 6),
        hiddenCount: Math.max(groupItems.length - 6, 0),
    }));
});

const getSelectionFolderLabel = (item: FileSystemObject) => {
    if (!item.path) {
        if (isGoogleDriveTab.value) return 'Google Drive';
        return isUserUploadsTab.value ? 'Current folder' : 'Generated Images';
    }

    const normalizedPath = item.path.replace(/\/$/, '');
    const parts = normalizedPath.split('/').filter(Boolean);

    if (parts.length <= 1) return 'Root';

    return `/${parts.slice(0, -1).join('/')}`;
};

// --- Drag Selection ---
type SelectionDragPoint = {
    x: number;
    y: number;
    clientX: number;
    clientY: number;
};

const DRAG_SELECT_THRESHOLD = 5;
const selectionDragStart = ref<SelectionDragPoint | null>(null);
const selectionDragCurrent = ref<SelectionDragPoint | null>(null);
const isDragSelecting = ref(false);
const dragSelectionAddsToExisting = ref(false);
const initialVisibleSelectedIds = ref(new Set<string>());
const suppressNextContentClick = ref(false);

const dragSelectionStyle = computed(() => {
    if (!selectionDragStart.value || !selectionDragCurrent.value) return {};

    const left = Math.min(selectionDragStart.value.x, selectionDragCurrent.value.x);
    const top = Math.min(selectionDragStart.value.y, selectionDragCurrent.value.y);
    const width = Math.abs(selectionDragStart.value.x - selectionDragCurrent.value.x);
    const height = Math.abs(selectionDragStart.value.y - selectionDragCurrent.value.y);

    return {
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
    };
});

const getContentPoint = (event: PointerEvent): SelectionDragPoint | null => {
    const contentArea = contentAreaRef.value;
    if (!contentArea) return null;

    const contentRect = contentArea.getBoundingClientRect();
    return {
        x: event.clientX - contentRect.left + contentArea.scrollLeft,
        y: event.clientY - contentRect.top + contentArea.scrollTop,
        clientX: event.clientX,
        clientY: event.clientY,
    };
};

const getDragSelectionClientRect = () => {
    if (!selectionDragStart.value || !selectionDragCurrent.value) return null;

    return {
        left: Math.min(selectionDragStart.value.clientX, selectionDragCurrent.value.clientX),
        right: Math.max(selectionDragStart.value.clientX, selectionDragCurrent.value.clientX),
        top: Math.min(selectionDragStart.value.clientY, selectionDragCurrent.value.clientY),
        bottom: Math.max(selectionDragStart.value.clientY, selectionDragCurrent.value.clientY),
    };
};

const rectsIntersect = (
    first: { left: number; right: number; top: number; bottom: number },
    second: { left: number; right: number; top: number; bottom: number },
) => {
    return !(
        first.right < second.left ||
        first.left > second.right ||
        first.bottom < second.top ||
        first.top > second.bottom
    );
};

const getDragSelectedItems = () => {
    const contentArea = contentAreaRef.value;
    const selectionRect = getDragSelectionClientRect();
    if (!contentArea || !selectionRect) return [];

    const selectedIds = new Set<string>();
    contentArea.querySelectorAll<HTMLElement>('[data-file-selectable="true"]').forEach((element) => {
        if (!rectsIntersect(selectionRect, element.getBoundingClientRect())) return;

        const itemId = element.dataset.fileId;
        if (itemId) selectedIds.add(itemId);
    });

    return visibleSelectableItems.value.filter((item) => selectedIds.has(item.id));
};

const applyDragSelection = () => {
    const draggedItems = getDragSelectedItems();

    if (!dragSelectionAddsToExisting.value) {
        replaceVisibleSelection(visibleSelectableItems.value, draggedItems);
        return;
    }

    const draggedItemIds = new Set(draggedItems.map((item) => item.id));
    replaceVisibleSelection(
        visibleSelectableItems.value,
        visibleSelectableItems.value.filter(
            (item) => initialVisibleSelectedIds.value.has(item.id) || draggedItemIds.has(item.id),
        ),
    );
};

const resetDragSelection = () => {
    selectionDragStart.value = null;
    selectionDragCurrent.value = null;
    isDragSelecting.value = false;
    dragSelectionAddsToExisting.value = false;
    initialVisibleSelectedIds.value = new Set();
    window.removeEventListener('pointermove', handleSelectionPointerMove);
    window.removeEventListener('pointerup', handleSelectionPointerUp);
};

const isDragSelectionBlockedTarget = (target: EventTarget | null) => {
    return (
        target instanceof HTMLElement &&
        Boolean(
            target.closest(
                'button, input, select, textarea, a, [contenteditable="true"], [data-file-draggable="true"]',
            ),
        )
    );
};

const handleSelectionPointerMove = (event: PointerEvent) => {
    if (!selectionDragStart.value) return;

    const currentPoint = getContentPoint(event);
    if (!currentPoint) return;

    selectionDragCurrent.value = currentPoint;

    const deltaX = currentPoint.clientX - selectionDragStart.value.clientX;
    const deltaY = currentPoint.clientY - selectionDragStart.value.clientY;
    const hasPassedThreshold = Math.hypot(deltaX, deltaY) >= DRAG_SELECT_THRESHOLD;

    if (!isDragSelecting.value && !hasPassedThreshold) return;

    if (!isDragSelecting.value) {
        isDragSelecting.value = true;
        closeContextMenu();
    }

    event.preventDefault();
    applyDragSelection();
};

const handleSelectionPointerUp = (event: PointerEvent) => {
    if (isDragSelecting.value) {
        const currentPoint = getContentPoint(event);
        if (currentPoint) selectionDragCurrent.value = currentPoint;

        event.preventDefault();
        applyDragSelection();
        suppressNextContentClick.value = true;
        window.setTimeout(() => {
            suppressNextContentClick.value = false;
        }, 0);
    }

    resetDragSelection();
};

const handleContentPointerDown = (event: PointerEvent) => {
    if (
        event.button !== 0 ||
        event.pointerType === 'touch' ||
        isContentLoading.value ||
        visibleSelectableItems.value.length === 0 ||
        isDragSelectionBlockedTarget(event.target)
    ) {
        return;
    }

    const startPoint = getContentPoint(event);
    if (!startPoint) return;

    selectionDragStart.value = startPoint;
    selectionDragCurrent.value = startPoint;
    dragSelectionAddsToExisting.value = event.ctrlKey || event.metaKey;
    initialVisibleSelectedIds.value = new Set(
        visibleSelectableItems.value.filter((item) => isSelected(item)).map((item) => item.id),
    );

    window.addEventListener('pointermove', handleSelectionPointerMove);
    window.addEventListener('pointerup', handleSelectionPointerUp);
};

const handleContentClickCapture = (event: MouseEvent) => {
    if (!suppressNextContentClick.value) return;

    event.preventDefault();
    event.stopPropagation();
    suppressNextContentClick.value = false;
};

const normalizePath = (path: string) => path.replace(/\/$/, '') || '/';

const buildAllUploadsBreadcrumbs = (folder: FileSystemObject) => {
    const rootFolder = breadcrumbs.value[0];
    if (!rootFolder || !folder.path) return [folder];

    const parts = normalizePath(folder.path).split('/').filter(Boolean);
    const folderBreadcrumbs: FileSystemObject[] = [rootFolder];

    parts.reduce((currentPath, part) => {
        const nextPath = `${currentPath === '/' ? '' : currentPath}/${part}`;
        const matchingFolder = allUploadItems.value.find(
            (item) => item.type === 'folder' && normalizePath(item.path ?? '') === nextPath,
        );

        if (matchingFolder) folderBreadcrumbs.push(matchingFolder);
        return nextPath;
    }, '/');

    if (folderBreadcrumbs[folderBreadcrumbs.length - 1]?.id !== folder.id) {
        folderBreadcrumbs.push(folder);
    }

    return folderBreadcrumbs;
};

const handleExplorerNavigate = (folder: FileSystemObject) => {
    if (isAllUploadsSearchMode.value) {
        void handleShortcutNavigate(
            { folder, breadcrumbs: buildAllUploadsBreadcrumbs(folder) },
            viewMode.value,
        );
        return;
    }

    void handleNavigate(folder, viewMode.value);
};

// --- Drag to Move ---
const dragMoveItems = ref<FileSystemObject[]>([]);
const dragMoveSourceId = ref<string | null>(null);
const dragMoveTargetId = ref<string | null>(null);
const isDragMoveActive = computed(() => dragMoveItems.value.length > 0);

const getDragMoveItems = (item: FileSystemObject) => {
    if (!canMoveFileManagerItem(item)) return [];

    if (isSelected(item)) {
        const movableSelectedItems = selectedItems.value.filter(canMoveFileManagerItem);
        if (movableSelectedItems.length > 0) return movableSelectedItems;
    }

    return [item];
};

const isDraggedMoveItem = (item: FileSystemObject) => {
    return dragMoveItems.value.some((draggedItem) => draggedItem.id === item.id);
};

const isFolderInsideDraggedFolder = (destination: FileSystemObject, draggedItem: FileSystemObject) => {
    if (draggedItem.type !== 'folder') return false;
    if (!destination.path || !draggedItem.path) return false;

    const destinationPath = normalizePath(destination.path);
    const draggedPath = normalizePath(draggedItem.path);
    return destinationPath === draggedPath || destinationPath.startsWith(`${draggedPath}/`);
};

const canDropMoveOnFolder = (destination: FileSystemObject) => {
    if (!isDragMoveActive.value || destination.type !== 'folder') return false;

    return dragMoveItems.value.every((draggedItem) => {
        return draggedItem.id !== destination.id && !isFolderInsideDraggedFolder(destination, draggedItem);
    });
};

const isDragMoveDropTarget = (folder: FileSystemObject) => {
    return dragMoveTargetId.value === folder.id && canDropMoveOnFolder(folder);
};

const resetDragMove = () => {
    dragMoveItems.value = [];
    dragMoveSourceId.value = null;
    dragMoveTargetId.value = null;
};

const handleItemDragStart = (event: DragEvent, item: FileSystemObject) => {
    const itemsToMove = getDragMoveItems(item);
    if (itemsToMove.length === 0) {
        event.preventDefault();
        return;
    }

    dragMoveItems.value = itemsToMove;
    dragMoveSourceId.value = item.id;
    dragMoveTargetId.value = null;
    isDraggingOver.value = false;
    closeContextMenu();

    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('application/x-meridian-file-move', itemsToMove.map((i) => i.id).join(','));
        event.dataTransfer.setData(
            'text/plain',
            itemsToMove.length === 1 ? itemsToMove[0].name : `${itemsToMove.length} items`,
        );
    }
};

const handleItemDragEnd = () => {
    window.setTimeout(resetDragMove, 0);
};

const handleDragMoveOver = (event: DragEvent, destination: FileSystemObject) => {
    if (!isDragMoveActive.value) return;

    if (canDropMoveOnFolder(destination)) {
        if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
        dragMoveTargetId.value = destination.id;
        return;
    }

    if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';
    if (dragMoveTargetId.value === destination.id) dragMoveTargetId.value = null;
};

const handleDragMoveLeave = (event: DragEvent, destination: FileSystemObject) => {
    const currentTarget = event.currentTarget as HTMLElement | null;
    const relatedTarget = event.relatedTarget as Node | null;
    if (currentTarget && relatedTarget && currentTarget.contains(relatedTarget)) return;
    if (dragMoveTargetId.value === destination.id) dragMoveTargetId.value = null;
};

const handleDragMoveDrop = async (event: DragEvent, destination: FileSystemObject) => {
    event.preventDefault();
    event.stopPropagation();

    if (!canDropMoveOnFolder(destination)) {
        resetDragMove();
        return;
    }

    const itemsToMove = [...dragMoveItems.value];
    resetDragMove();
    await handleMoveItems(itemsToMove, destination, selectedFiles);
};

// --- Context Menu Handlers ---
const handleContextMenu = (event: MouseEvent, item: FileSystemObject) => {
    showContextMenu.value = true;
    contextMenuPos.value = { x: event.clientX, y: event.clientY };
    contextMenuItem.value = item;
};

const closeContextMenu = () => {
    showContextMenu.value = false;
    contextMenuItem.value = null;
};

const handleContextOpen = (item: FileSystemObject) => {
    closeContextMenu();
    if (item.type === 'folder' && (isUserUploadsTab.value || isGoogleDriveTab.value)) {
        handleExplorerNavigate(item);
    } else {
        handleSelect(item);
    }
};

const handleContextSelect = (item: FileSystemObject) => {
    closeContextMenu();
    if (item.type === 'folder') {
        void handleSelectFolderContents(item);
        return;
    }

    handleSelect(item);
};

const isFolderPinned = (item: FileSystemObject) => {
    return pinnedFolders.value.some((shortcut) => shortcut.folder.id === item.id);
};

const handleContextPin = (item: FileSystemObject) => {
    closeContextMenu();
    if (item.type !== 'folder') return;
    togglePinnedFolder({ folder: item, breadcrumbs: [...breadcrumbs.value, item] });
};

const handleContextRename = (item: FileSystemObject) => {
    closeContextMenu();
    if (!isUserUploadsTab.value) return;
    startRename(item);
};

const handleContextDelete = (item: FileSystemObject) => {
    closeContextMenu();
    if (!isUserUploadsTab.value) return;
    handleDeleteItem(item, selectedFiles);
};

const handleContextDownload = (item: FileSystemObject) => {
    closeContextMenu();
    handleDownload(item);
};

const handleContextView = (item: FileSystemObject) => {
    closeContextMenu();
    if (item.type !== 'file') return;
    const url = item.source === 'google_drive'
        ? `/api/google-drive/view/${item.id}`
        : `/api/auth/refresh/files/view/${item.id}`;
    window.open(url, '_blank', 'noopener,noreferrer');
};

const openFileAction = (action: 'move' | 'copy', actionItems: FileSystemObject[]) => {
    if (actionItems.length === 0 || !isUserUploadsTab.value) return;
    pendingFileAction.value = action;
    pendingFileActionItems.value = actionItems;
};

const closeFileAction = () => {
    pendingFileAction.value = null;
    pendingFileActionItems.value = [];
};

const handleContextMove = (item: FileSystemObject) => {
    closeContextMenu();
    openFileAction('move', [item]);
};

const handleContextCopy = (item: FileSystemObject) => {
    closeContextMenu();
    openFileAction('copy', [item]);
};

const handleSelectedMove = () => openFileAction('move', selectedMovableItems.value);
const handleSelectedCopy = () => openFileAction('copy', selectedMovableItems.value);

const handleSelectAllVisible = () => {
    selectItems(visibleSelectableItems.value);
};

const handleListSelect = (item: FileSystemObject, event?: MouseEvent | KeyboardEvent) => {
    if (event?.shiftKey) {
        handleRangeSelect(item, filteredAndSortedItems.value);
        return;
    }

    handleSelect(item);
};

const handleFileActionSubmit = async (destinationFolder: FileSystemObject) => {
    if (pendingFileAction.value === 'move') {
        await handleMoveItems(pendingFileActionItems.value, destinationFolder, selectedFiles);
    } else if (pendingFileAction.value === 'copy') {
        await handleCopyItems(pendingFileActionItems.value, destinationFolder);
    }
    closeFileAction();
};

const isTypingTarget = (target: EventTarget | null) => {
    return target instanceof HTMLElement && target.closest('input, textarea, [contenteditable="true"]');
};

const handleKeyboardShortcuts = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null;

    if (event.key === 'F2' && isUserUploadsTab.value && !isRenaming.value && !isTypingTarget(target)) {
        if (selectedItems.value.length === 1) {
            event.preventDefault();
            startRename(selectedItems.value[0]);
        }
        return;
    }

    if (isTypingTarget(target)) return;

    if (event.key === '/') {
        event.preventDefault();
        toolbarRef.value?.focusSearchInput();
        return;
    }

    if (event.key === 'Delete' && isUserUploadsTab.value && selectedItems.value.length > 0) {
        event.preventDefault();
        void handleDeleteItems(selectedItems.value, selectedFiles);
        return;
    }

    if (event.altKey && event.key === 'ArrowLeft') {
        event.preventDefault();
        void goBack(viewMode.value);
        return;
    }

    if (event.altKey && event.key === 'ArrowRight') {
        event.preventDefault();
        void goForward(viewMode.value);
    }
};

// --- Drag & Drop ---
const handleContentDragOver = (event: DragEvent) => {
    if (isDragMoveActive.value) {
        if (event.dataTransfer) event.dataTransfer.dropEffect = 'none';
        return;
    }

    isDraggingOver.value = true;
};

const handleContentDragLeave = () => {
    if (isDragMoveActive.value) return;
    isDraggingOver.value = false;
};

const handleFileDrop = async (event: DragEvent) => {
    isDraggingOver.value = false;
    if (isDragMoveActive.value) {
        resetDragMove();
        return;
    }

    if (!isUserUploadsTab.value || !currentFolder.value) return;

    const files = event.dataTransfer?.files;
    if (files && files.length) {
        const mockTarget = {
            files: files,
            value: '',
        } as unknown as HTMLInputElement;
        await handleFileUploadFromEvent({ target: mockTarget } as unknown as Event);
    }
};

// --- Lifecycle ---
onMounted(() => {
    initialize(viewMode.value);
    window.addEventListener('keydown', handleKeyboardShortcuts);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyboardShortcuts);
    resetDragSelection();
    resetDragMove();
});

const confirmSelection = () => {
    emit('close', Array.from(selectedFiles));
};

const triggerUpload = () => uploadInputRef.value?.click();
const triggerFolderUpload = () => uploadFolderInputRef.value?.click();
</script>

<template>
    <div class="flex h-full w-full flex-col gap-4">
        <!-- Hidden Inputs for Uploads -->
        <input
            ref="uploadInputRef"
            type="file"
            multiple
            class="hidden"
            @change="handleFileUploadFromEvent"
        />
        <input
            ref="uploadFolderInputRef"
            type="file"
            multiple
            webkitdirectory
            directory
            class="hidden"
            @change="handleFileUploadFromEvent"
        />

        <!-- Context Menu -->
        <UiGraphNodeUtilsFilePromptFileContextMenu
            v-if="showContextMenu && contextMenuItem"
            :position="contextMenuPos"
            :item="contextMenuItem"
            :can-move-copy="isUserUploadsTab"
            :can-copy="!isStorageFull"
            :can-manage="isUserUploadsTab"
            :is-pinned="isFolderPinned(contextMenuItem)"
            @close="closeContextMenu"
            @open="handleContextOpen"
            @select="handleContextSelect"
            @pin="handleContextPin"
            @view="handleContextView"
            @rename="handleContextRename"
            @download="handleContextDownload"
            @move="handleContextMove"
            @copy="handleContextCopy"
            @delete="handleContextDelete"
        />

        <UiGraphNodeUtilsFilePromptFileFolderPickerModal
            :is-open="pendingFileAction !== null"
            :title="pendingFileAction === 'move' ? 'Move Items' : 'Copy Items'"
            :submit-label="pendingFileAction === 'move' ? 'Move' : 'Copy'"
            @close="closeFileAction"
            @submit="handleFileActionSubmit"
        />

        <UiGraphNodeUtilsFilePromptFileConflictModal
            :is-open="conflictRequest !== null"
            :title="conflictRequest?.title ?? ''"
            :description="conflictRequest?.description ?? ''"
            :conflicts="conflictRequest?.conflicts ?? []"
            @resolve="resolveConflictPolicy"
            @cancel="cancelConflictPolicy"
        />

        <!-- Header -->
        <div class="border-stone-gray/15 mb-1 flex items-center justify-between gap-4 border-b pb-3">
            <div class="flex items-center gap-3">
                <div class="bg-ember-glow/10 flex h-10 w-10 items-center justify-center rounded-xl">
                    <UiIcon name="MajesticonsAttachment" class="text-ember-glow h-5 w-5" />
                </div>
                <div>
                    <h2 class="text-soft-silk text-lg font-bold">Select Attachments</h2>
                    <p class="text-stone-gray/50 text-xs">Browse, upload, and choose files to attach.</p>
                </div>
            </div>
            <div
                v-if="isStorageFull"
                class="flex items-center gap-2 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs font-semibold
                    text-red-400 ring-1 ring-red-500/20"
            >
                <UiIcon name="MdiAlertCircle" class="h-4 w-4" />
                <span>Storage Full</span>
            </div>
        </div>

        <!-- Rename Modal -->
        <UiGraphNodeUtilsFilePromptFileManagerRenameModal
            v-model="renameInput"
            :is-open="isRenaming"
            @close="isRenaming = false"
            @submit="submitRename"
        />

        <!-- Main Layout -->
        <div class="flex flex-1 gap-4 overflow-hidden">
            <!-- Sidebar -->
                <UiGraphNodeUtilsFilePromptFileManagerSidebar
                    :active-tab="activeTab"
                    :active-google-drive-section="activeGoogleDriveSection"
                    :is-user-uploads-tab="isUserUploadsTab"
                    :is-google-drive-tab="isGoogleDriveTab"
                    :pinned-folders="pinnedFolders"
                    :recent-folders="recentFolders"
                    @switch-tab="switchTab($event, viewMode)"
                    @switch-google-drive-section="switchGoogleDriveSection($event, viewMode)"
                    @navigate-folder="handleShortcutNavigate($event, viewMode)"
                    @toggle-pin="togglePinnedFolder"
                />

            <!-- Content Area -->
            <div class="flex min-w-0 flex-1 flex-col gap-4">
                <!-- Toolbar -->
                <UiGraphNodeUtilsFilePromptFileManagerToolbar
                    ref="toolbarRef"
                    v-model:search-query="searchQuery"
                    v-model:sort-by="sortBy"
                    v-model:sort-direction="sortDirection"
                    v-model:file-type-filter="fileTypeFilter"
                    v-model:folders-first="foldersFirst"
                    v-model:search-scope="searchScope"
                    v-model:is-creating-folder="isCreatingFolder"
                    v-model:new-folder-name="newFolderName"
                    :breadcrumbs="breadcrumbs"
                    :view-mode="viewMode"
                    :can-go-back="canGoBack"
                    :can-go-forward="canGoForward"
                    :selected-count="selectedItems.length"
                    :selected-download-count="selectedDownloadItems.length"
                    :selected-movable-count="selectedMovableItems.length"
                    :is-user-uploads-tab="isUserUploadsTab"
                    :is-google-drive-tab="isGoogleDriveTab"
                    :is-storage-full="isStorageFull"
                    :is-all-uploads-loading="isAllUploadsLoading"
                    :is-drag-move-active="isDragMoveActive"
                    :drag-move-target-id="dragMoveTargetId"
                    @navigate="handleNavigate($event, viewMode)"
                    @go-back="goBack(viewMode)"
                    @go-forward="goForward(viewMode)"
                    @toggle-view-mode="toggleViewMode"
                    @delete-selected="handleDeleteItems(selectedItems, selectedFiles)"
                    @download-selected="handleDownloadItems(selectedDownloadItems)"
                    @move-selected="handleSelectedMove"
                    @copy-selected="handleSelectedCopy"
                    @create-folder="handleCreateFolder"
                    @trigger-upload="triggerUpload"
                    @trigger-folder-upload="triggerFolderUpload"
                    @drag-move-over="handleDragMoveOver"
                    @drag-move-leave="handleDragMoveLeave"
                    @drag-move-drop="handleDragMoveDrop"
                />

                <!-- File Grid/List -->
                <div
                    ref="contentAreaRef"
                    class="bg-obsidian/40 border-stone-gray/15 dark-scrollbar relative min-h-0 grow
                        select-none overflow-y-auto rounded-xl border p-4 transition-colors"
                    :class="isDraggingOver && isUserUploadsTab ? 'border-ember-glow/40' : ''"
                    @click.capture="handleContentClickCapture"
                    @pointerdown="handleContentPointerDown"
                    @dragover.prevent="handleContentDragOver"
                    @dragleave.prevent="handleContentDragLeave"
                    @drop.prevent="handleFileDrop"
                >
                    <!-- Selection Marquee -->
                    <div
                        v-if="isDragSelecting"
                        class="border-ember-glow/60 bg-ember-glow/10 pointer-events-none absolute z-40
                            rounded-md border"
                        :style="dragSelectionStyle"
                    />

                    <!-- Drag Overlay -->
                    <div
                        v-if="isDraggingOver && isUserUploadsTab && !isDragMoveActive"
                        class="pointer-events-none absolute inset-0 z-50 flex flex-col items-center
                            justify-center gap-3 rounded-xl border-2 border-dashed text-center
                            backdrop-blur transition-all duration-200 ease-in-out"
                        :class="
                            isStorageFull
                                ? 'border-red-500/50! text-red-400!'
                                : 'border-ember-glow/50! text-soft-silk/60!'
                        "
                    >
                        <div
                            class="flex h-16 w-16 items-center justify-center rounded-2xl"
                            :class="isStorageFull ? 'bg-red-500/10' : 'bg-ember-glow/10'"
                        >
                            <UiIcon
                                :name="isStorageFull ? 'MdiCancel' : 'UilUpload'"
                                class="h-8 w-8"
                            />
                        </div>
                        <p v-if="!isStorageFull" class="text-sm font-medium">Drop files here to upload</p>
                        <p v-else class="text-sm font-medium">Storage Full</p>
                    </div>

                    <!-- Loading -->
                    <div
                        v-if="isContentLoading"
                        class="text-stone-gray/50 flex h-full flex-col items-center justify-center gap-3"
                    >
                        <UiIcon name="MaterialSymbolsProgressActivity" class="h-8 w-8 animate-spin" />
                        <p class="text-sm">Loading...</p>
                    </div>

                    <!-- Content -->
                    <template v-else-if="filteredAndSortedItems.length > 0">
                        <!-- Grid / Gallery -->
                        <div
                            v-if="viewMode === 'grid' || viewMode === 'gallery'"
                            class="grid"
                            :class="
                                viewMode === 'gallery'
                                    ? 'grid-cols-[repeat(auto-fill,minmax(10rem,1fr))] gap-1.5'
                                    : 'grid-cols-[repeat(auto-fill,minmax(7rem,1fr))] gap-2'
                            "
                        >
                            <UiGraphNodeUtilsFilePromptFileItem
                                v-for="item in filteredAndSortedItems"
                                :key="item.id"
                                :data-file-id="item.id"
                                :data-file-selectable="item.type === 'file' ? 'true' : undefined"
                                :item="item"
                                :is-selected="isSelected(item) || isFolderFullySelected(item)"
                                :has-selected-descendants="hasSelectedDescendants(item)"
                                :preview-url="imagePreviews[item.id]"
                                :view-mode="viewMode === 'gallery' ? 'gallery' : 'grid'"
                                :can-drag="canMoveFileManagerItem(item)"
                                :is-dragging="isDraggedMoveItem(item)"
                                :is-drag-move-active="isDragMoveActive"
                                :is-drop-target="isDragMoveDropTarget(item)"
                                @navigate="handleExplorerNavigate"
                                @select="handleSelect"
                                @select-folder-contents="handleSelectFolderContents"
                                @delete="handleDeleteItem($event, selectedFiles)"
                                @contextmenu="handleContextMenu"
                                @drag-move-start="handleItemDragStart"
                                @drag-move-end="handleItemDragEnd"
                                @drag-move-over="handleDragMoveOver"
                                @drag-move-leave="handleDragMoveLeave"
                                @drag-move-drop="handleDragMoveDrop"
                            />
                        </div>

                        <!-- List -->
                        <div v-else class="flex h-full flex-col">
                            <div
                                class="text-stone-gray/50 border-stone-gray/15 mb-1 grid
                                    grid-cols-[1fr_8rem_8rem_10rem] gap-4 border-b px-3 py-2 text-[11px]
                                    font-semibold tracking-wider uppercase"
                            >
                                <div class="pl-7">Name</div>
                                <div>Size</div>
                                <div>Type</div>
                                <div>Date Modified</div>
                            </div>
                            <div class="flex flex-col gap-1 pb-4">
                                <UiGraphNodeUtilsFilePromptFileListItem
                                    v-for="item in filteredAndSortedItems"
                                    :key="item.id"
                                    :data-file-id="item.id"
                                    :data-file-selectable="item.type === 'file' ? 'true' : undefined"
                                    :item="item"
                                    :is-selected="isSelected(item) || isFolderFullySelected(item)"
                                    :has-selected-descendants="hasSelectedDescendants(item)"
                                    :can-drag="canMoveFileManagerItem(item)"
                                    :is-dragging="isDraggedMoveItem(item)"
                                    :is-drag-move-active="isDragMoveActive"
                                    :is-drop-target="isDragMoveDropTarget(item)"
                                    @navigate="handleExplorerNavigate"
                                    @select="handleListSelect"
                                    @select-folder-contents="handleSelectFolderContents"
                                    @delete="handleDeleteItem($event, selectedFiles)"
                                    @contextmenu="handleContextMenu"
                                    @drag-move-start="handleItemDragStart"
                                    @drag-move-end="handleItemDragEnd"
                                    @drag-move-over="handleDragMoveOver"
                                    @drag-move-leave="handleDragMoveLeave"
                                    @drag-move-drop="handleDragMoveDrop"
                                />
                            </div>
                        </div>
                    </template>

                    <!-- Empty State -->
                    <div v-else class="pointer-events-none flex h-full flex-col items-center justify-center gap-3">
                        <template v-if="hasActiveFilters">
                            <UiIcon name="MaterialSymbolsSearchOff" class="text-stone-gray/30 h-12 w-12" />
                            <p class="text-stone-gray/50 text-sm font-medium">No items match your filters.</p>
                            <p class="text-stone-gray/30 text-xs">Try adjusting your search or filter criteria.</p>
                        </template>
                    <template v-else-if="isUserUploadsTab">
                            <UiIcon name="MdiFolderOutline" class="text-stone-gray/25 h-12 w-12" />
                            <p class="text-stone-gray/50 text-sm font-medium">This folder is empty.</p>
                            <p class="text-stone-gray/30 max-w-xs text-xs text-center leading-relaxed">
                                Create a new folder, upload files using the toolbar, or drag and drop
                                files here to get started.
                            </p>
                        </template>
                        <template v-else-if="isGoogleDriveTab">
                            <UiIcon name="CiGoogle" class="text-stone-gray/25 h-12 w-12" />
                            <p class="text-stone-gray/50 text-sm font-medium">
                                {{ isGoogleDriveConnected ? 'No Google Drive files found.' : 'Google Drive is not connected.' }}
                            </p>
                            <p class="text-stone-gray/30 max-w-xs text-xs text-center leading-relaxed">
                                {{ isGoogleDriveConnected
                                    ? 'Browse Drive folders or search across your accessible files.'
                                    : 'Connect Google Drive in settings to browse external file references.' }}
                            </p>
                            <p v-if="googleDriveEmail" class="text-stone-gray/40 text-xs">
                                Connected as {{ googleDriveEmail }}
                            </p>
                        </template>
                        <template v-else>
                            <UiIcon name="MynauiSparklesSolid" class="text-stone-gray/25 h-12 w-12" />
                            <p class="text-stone-gray/50 text-sm font-medium">No generated images found.</p>
                            <p class="text-stone-gray/30 text-xs">Images created by generation tools will appear here.</p>
                        </template>
                    </div>
                </div>

                <!-- Upload Progress -->
                <UiGraphNodeUtilsFilePromptFileUploadProgress
                    :is-uploading="isUploading"
                    :status="uploadStatus"
                    :total-files="uploadTotalFiles"
                    :completed-files="uploadCompletedFiles"
                    :failed-files="uploadFailedFiles"
                    :current-file-name="currentFileName"
                    :current-file-progress="currentFileProgress"
                    :errors="uploadErrors"
                    @dismiss="resetUploadState"
                />

                <!-- Selection Summary -->
                <Transition
                    enter-active-class="transition duration-200 ease-out"
                    enter-from-class="opacity-0 translate-y-2"
                    enter-to-class="opacity-100 translate-y-0"
                    leave-active-class="transition duration-150 ease-in"
                    leave-from-class="opacity-100 translate-y-0"
                    leave-to-class="opacity-0 translate-y-2"
                >
                    <div
                        v-if="selectedItems.length > 0"
                        class="border-ember-glow/20 bg-ember-glow/5 max-h-36 shrink-0 overflow-y-auto
                            rounded-xl border p-3"
                    >
                        <div class="mb-2 flex items-center justify-between gap-3">
                            <div class="flex items-center gap-2">
                                <div class="bg-ember-glow flex h-5 w-5 items-center justify-center rounded-full">
                                    <UiIcon
                                        name="MaterialSymbolsCheckSmallRounded"
                                        class="text-obsidian h-3.5 w-3.5"
                                    />
                                </div>
                                <p class="text-soft-silk text-sm font-semibold">
                                    {{ selectedItems.length }} selected
                                </p>
                            </div>
                            <p class="text-stone-gray/60 text-xs">
                                {{ selectedDownloadItems.length }} file{{
                                    selectedDownloadItems.length === 1 ? '' : 's'
                                }}
                            </p>
                        </div>

                        <div class="flex flex-col gap-2">
                            <div
                                v-for="group in selectedGroups"
                                :key="group.folder"
                                class="flex flex-wrap items-center gap-2"
                            >
                                <span
                                    class="text-stone-gray/60 min-w-28 truncate text-xs font-medium"
                                    :title="group.folder"
                                >
                                    {{ group.folder }} · {{ group.totalCount }}
                                </span>
                                <span
                                    v-for="item in group.items"
                                    :key="item.id"
                                    class="bg-stone-gray/10 text-soft-silk flex max-w-44 items-center gap-1.5
                                        rounded-full px-2.5 py-1 text-xs"
                                    :title="item.name"
                                >
                                    <UiIcon
                                        :name="
                                            item.type === 'folder' ? 'MdiFolderOutline' : 'MdiFileOutline'
                                        "
                                        class="h-3.5 w-3.5 shrink-0 text-stone-gray/60"
                                    />
                                    <span class="truncate">{{ item.name }}</span>
                                </span>
                                <span v-if="group.hiddenCount > 0" class="text-stone-gray/50 text-xs font-medium">
                                    +{{ group.hiddenCount }} more
                                </span>
                            </div>
                        </div>
                    </div>
                </Transition>

                <!-- Footer Actions -->
                <div class="mt-auto flex items-center justify-between gap-3 pt-2">
                    <div class="flex items-center gap-2">
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray/80 hover:text-soft-silk
                                flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium
                                transition-colors duration-200 disabled:cursor-not-allowed
                                disabled:opacity-40"
                            :disabled="
                                visibleSelectableItems.length === 0 ||
                                selectedVisibleCount === visibleSelectableItems.length
                            "
                            title="Select all visible files in the current result"
                            @click="handleSelectAllVisible"
                        >
                            <UiIcon name="MaterialSymbolsSelectAllRounded" class="h-4 w-4" />
                            Select all visible
                        </button>
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray/80 hover:text-soft-silk
                                flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium
                                transition-colors duration-200 disabled:cursor-not-allowed
                                disabled:opacity-40"
                            :disabled="selectedItems.length === 0"
                            @click="clearSelection"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                            Clear
                        </button>
                    </div>

                    <div class="flex justify-end gap-3">
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray/80 hover:text-soft-silk
                                rounded-lg px-4 py-2.5 text-sm font-medium transition-colors duration-200"
                            @click="$emit('close', initialSelectedFiles)"
                        >
                            Cancel
                        </button>
                        <button
                            class="bg-ember-glow text-obsidian flex items-center gap-2 rounded-lg px-4 py-2.5
                                text-sm font-semibold transition-all duration-200 hover:brightness-110"
                            @click="confirmSelection"
                        >
                            <UiIcon name="MaterialSymbolsCheckSmallRounded" class="h-4 w-4" />
                            Confirm Selection ({{ selectedFiles.size }})
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
