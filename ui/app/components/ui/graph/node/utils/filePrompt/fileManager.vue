<script lang="ts" setup>
import { AnimatePresence, motion } from 'motion-v';

// --- Props & Emits ---
const props = defineProps<{
    initialSelectedFiles?: FileSystemObject[];
}>();
const emit = defineEmits(['close']);

// --- Stores ---
const usageStore = useUsageStore();
const { storageUsage } = storeToRefs(usageStore);

// --- Composables ---
const {
    getRootFolder,
    getFolderContents,
    getGeneratedImages,
    createFolder,
    uploadFile,
    deleteFileSystemObject,
    renameFileSystemObject,
    getFileBlob,
} = useAPI();
const { success, error } = useToast();

// --- Types ---
type ViewTab = 'uploads' | 'generated';
type ViewMode = 'grid' | 'gallery' | 'list';

// --- State ---
const activeTab = ref<ViewTab>('uploads');
const currentFolder = ref<FileSystemObject | null>(null);
const items = ref<FileSystemObject[]>([]);
const breadcrumbs = ref<FileSystemObject[]>([]);
const selectedFiles = ref<Set<FileSystemObject>>(
    new Set(props.initialSelectedFiles?.map((f) => ({ ...f })) || []),
);
const isLoading = ref(true);
const isCreatingFolder = ref(false);
const newFolderName = ref('');
const isRenaming = ref(false);
const renamingItem = ref<FileSystemObject | null>(null);
const renameInput = ref('');
const uploadInputRef = ref<HTMLInputElement | null>(null);
const uploadFolderInputRef = ref<HTMLInputElement | null>(null);
const searchQuery = ref('');
const sortBy = ref<'name' | 'date'>('name');
const sortDirection = ref<'asc' | 'desc'>('asc');
const viewMode = ref<ViewMode>('grid');
const isDraggingOver = ref(false);
const imagePreviews = ref<Record<string, string>>({});

// Context Menu State
const showContextMenu = ref(false);
const contextMenuPos = ref({ x: 0, y: 0 });
const contextMenuItem = ref<FileSystemObject | null>(null);

// --- Computed ---
const isStorageFull = computed(() => storageUsage.value.percentage >= 100);

const filteredAndSortedItems = computed(() => {
    // Filter by search query
    const filtered = items.value.filter((item) =>
        item.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
    );

    // Sort
    return filtered.sort((a, b) => {
        if (a.type === 'folder' && b.type !== 'folder') return -1;
        if (a.type !== 'folder' && b.type === 'folder') return 1;

        let comparison = 0;
        if (sortBy.value === 'name') {
            comparison = a.name.localeCompare(b.name);
        } else if (sortBy.value === 'date') {
            const dateA = new Date(a.created_at).getTime();
            const dateB = new Date(b.created_at).getTime();
            comparison = dateA - dateB;
        }

        return sortDirection.value === 'asc' ? comparison : -comparison;
    });
});

const isUserUploadsTab = computed(() => activeTab.value === 'uploads');

// --- Methods ---
const isImage = (file: FileSystemObject) => {
    if (file.type !== 'file') return false;
    if (file.content_type?.startsWith('image/')) return true;
    const ext = file.name.split('.').pop()?.toLowerCase();
    return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext || '');
};

const hasSelectedDescendants = (item: FileSystemObject) => {
    if (item.type !== 'folder') return false;
    if (!item.path) return false;

    const folderPath = item.path.endsWith('/') ? item.path : item.path + '/';

    return Array.from(selectedFiles.value).some((file) => {
        return file.path && file.path.startsWith(folderPath);
    });
};

const loadImagePreviews = async (files: FileSystemObject[]) => {
    // Only load previews in grid or gallery mode to save resources
    if (viewMode.value === 'list') return;

    files.forEach(async (file) => {
        if (isImage(file) && !imagePreviews.value[file.id]) {
            try {
                const blob = await getFileBlob(file.id);
                imagePreviews.value[file.id] = URL.createObjectURL(blob);
            } catch (e) {
                console.error(`Failed to load preview for ${file.name}`, e);
            }
        }
    });
};

const loadGeneratedImages = async () => {
    isLoading.value = true;
    searchQuery.value = '';
    currentFolder.value = null;
    breadcrumbs.value = [];

    try {
        items.value = await getGeneratedImages();
        loadImagePreviews(items.value);
        usageStore.fetchUsage();
    } catch (e) {
        console.error(e);
        error('Failed to load generated images.');
    } finally {
        isLoading.value = false;
    }
};

const loadFolder = async (folder: FileSystemObject) => {
    if (!folder) return;
    isLoading.value = true;
    searchQuery.value = '';
    try {
        currentFolder.value = folder;
        const contents = await getFolderContents(folder.id);
        items.value = contents;
        loadImagePreviews(contents);
        // Refresh usage
        usageStore.fetchUsage();
    } catch (e) {
        console.error(e);
        error('Failed to load folder contents.');
    } finally {
        isLoading.value = false;
    }
};

const switchTab = async (tab: ViewTab) => {
    if (activeTab.value === tab) return;
    activeTab.value = tab;

    if (tab === 'generated') {
        await loadGeneratedImages();
    } else {
        try {
            isLoading.value = true;
            const root = await getRootFolder();
            breadcrumbs.value = [root];
            await loadFolder(root);
        } catch {
            error('Failed to load root directory.');
            isLoading.value = false;
        }
    }
};

const initialize = async () => {
    // Load View Mode
    const savedViewMode = localStorage.getItem('meridian-file-view-mode');
    if (savedViewMode === 'grid' || savedViewMode === 'list' || savedViewMode === 'gallery') {
        viewMode.value = savedViewMode as ViewMode;
    }

    // Default to uploads
    try {
        const root = await getRootFolder();
        breadcrumbs.value = [root];
        await loadFolder(root);
    } catch (e) {
        console.error(e);
        error('Failed to load root directory.');
        isLoading.value = false;
    }
};

const handleNavigate = async (folder: FileSystemObject) => {
    if (!isUserUploadsTab.value) return;

    const breadcrumbIndex = breadcrumbs.value.findIndex((b) => b.id === folder.id);
    if (breadcrumbIndex > -1) {
        breadcrumbs.value = breadcrumbs.value.slice(0, breadcrumbIndex + 1);
    } else {
        breadcrumbs.value.push(folder);
    }
    await loadFolder(folder);
};

const handleSelect = (file: FileSystemObject) => {
    const existing = [...selectedFiles.value].find((f) => f.id === file.id);
    if (existing) {
        selectedFiles.value.delete(existing);
    } else {
        selectedFiles.value.add(file);
    }
};

const handleSelectFolderContents = async (folder: FileSystemObject) => {
    try {
        const contents = await getFolderContents(folder.id);
        const files = contents.filter((item) => item.type === 'file');

        if (files.length === 0) {
            success(`No files found in "${folder.name}".`);
            return;
        }

        let addedCount = 0;
        const currentIds = new Set([...selectedFiles.value].map((f) => f.id));

        files.forEach((file) => {
            if (!currentIds.has(file.id)) {
                selectedFiles.value.add(file);
                addedCount++;
            }
        });

        if (addedCount > 0) {
            success(`Added ${addedCount} files from "${folder.name}" to selection.`);
        } else {
            success(`All files in "${folder.name}" are already selected.`);
        }
    } catch (e) {
        console.error(e);
        error(`Failed to select contents of "${folder.name}".`);
    }
};

const isSelected = (item: FileSystemObject) => {
    return [...selectedFiles.value].some((f) => f.id === item.id);
};

const confirmSelection = () => {
    emit('close', Array.from(selectedFiles.value));
};

const handleCreateFolder = async () => {
    if (!isUserUploadsTab.value) return;
    if (!newFolderName.value.trim() || !currentFolder.value) return;
    try {
        const newFolder = await createFolder(newFolderName.value.trim(), currentFolder.value.id);
        items.value.unshift(newFolder);
        success(`Folder "${newFolder.name}" created.`);
    } catch (e) {
        console.error(e);
        error('Failed to create folder.');
    } finally {
        isCreatingFolder.value = false;
        newFolderName.value = '';
    }
};

const triggerUpload = () => {
    if (!isUserUploadsTab.value) return;
    if (isStorageFull.value) {
        error('Storage limit reached. Please delete files or upgrade to Premium.', {
            title: 'Storage Full',
        });
        return;
    }
    uploadInputRef.value?.click();
};

const triggerFolderUpload = () => {
    if (!isUserUploadsTab.value) return;
    if (isStorageFull.value) {
        error('Storage limit reached. Please delete files or upgrade to Premium.', {
            title: 'Storage Full',
        });
        return;
    }
    uploadFolderInputRef.value?.click();
};

const handleFileUpload = async (file: File, parentId: string) => {
    if (isStorageFull.value) {
        error('Storage limit reached.', { title: 'Storage Full' });
        return;
    }

    try {
        const newFile = await uploadFile(file, parentId);
        if (currentFolder.value && parentId === currentFolder.value.id) {
            items.value.push(newFile);
            loadImagePreviews([newFile]);
        }
        success(`File "${newFile.name}" uploaded.`);
    } catch (err) {
        const detail =
            (err as { data?: { detail?: string } })?.data?.detail ||
            (err as { message?: string })?.message ||
            '';
        console.error(`Failed to upload file ${file.name}:`, err);
        error(`Failed to upload file ${file.name}. ${detail}`, {
            title: 'Upload Error',
        });
    }
};

const handleFileUploadFromEvent = async (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (!target.files || target.files.length === 0 || !currentFolder.value) return;

    if (isStorageFull.value) {
        error('Storage limit reached.', { title: 'Storage Full' });
        target.value = '';
        return;
    }

    const files = Array.from(target.files);

    const filesByPath: Record<string, File[]> = {};
    const pathsToCreate = new Set<string>();

    for (const file of files) {
        let path = '';
        if (file.webkitRelativePath) {
            const parts = file.webkitRelativePath.split('/');
            parts.pop();
            if (parts.length > 0) {
                path = parts.join('/');
            }
        }

        if (!filesByPath[path]) {
            filesByPath[path] = [];
        }
        filesByPath[path].push(file);

        if (path) {
            const parts = path.split('/');
            let currentPath = '';
            for (const part of parts) {
                currentPath = currentPath ? `${currentPath}/${part}` : part;
                pathsToCreate.add(currentPath);
            }
        }
    }

    const sortedPaths = Array.from(pathsToCreate).sort((a, b) => a.length - b.length);

    const folderIdMap: Record<string, string> = {
        '': currentFolder.value.id,
    };

    for (const path of sortedPaths) {
        if (folderIdMap[path]) continue;

        const parts = path.split('/');
        const folderName = parts.pop()!;
        const parentPath = parts.join('/');
        const parentId = folderIdMap[parentPath];

        if (!parentId) {
            console.warn(`Skipping ${path}: Parent ID not found.`);
            continue;
        }

        let existingFolder = undefined;
        if (parentPath === '') {
            existingFolder = items.value.find((i) => i.type === 'folder' && i.name === folderName);
        }

        if (existingFolder) {
            folderIdMap[path] = existingFolder.id;
        } else {
            try {
                const newFolder = await createFolder(folderName, parentId);
                folderIdMap[path] = newFolder.id;

                if (parentId === currentFolder.value.id) {
                    items.value.unshift(newFolder);
                }
            } catch {
                try {
                    const contents = await getFolderContents(parentId);
                    const existing = contents.find(
                        (i) => i.type === 'folder' && i.name === folderName,
                    );
                    if (existing) {
                        folderIdMap[path] = existing.id;
                    }
                } catch (err) {
                    console.error(`Failed to resolve folder ${path}`, err);
                }
            }
        }
    }

    for (const [path, fileList] of Object.entries(filesByPath)) {
        const targetId = folderIdMap[path];
        if (!targetId) {
            console.error(`Target folder not found for path: ${path}`);
            continue;
        }

        for (const file of fileList) {
            await handleFileUpload(file, targetId);
        }
    }

    usageStore.fetchUsage();

    target.value = '';
};

const handleDeleteItem = async (itemToDelete: FileSystemObject) => {
    if (
        !window.confirm(
            `Are you sure you want to delete "${itemToDelete.name}"? This action cannot be undone.`,
        )
    )
        return;

    try {
        await deleteFileSystemObject(itemToDelete.id);
        // Remove from local state for immediate UI update
        items.value = items.value.filter((item) => item.id !== itemToDelete.id);
        // Also remove from selection if it was selected
        const selectedItem = [...selectedFiles.value].find((f) => f.id === itemToDelete.id);
        if (selectedItem) {
            selectedFiles.value.delete(selectedItem);
        }
        success(`"${itemToDelete.name}" has been deleted.`);
        usageStore.fetchUsage();
    } catch (err) {
        error(`Failed to delete "${itemToDelete.name}".`);
        console.error(err);
    }
};

const handleFileDrop = async (event: DragEvent) => {
    isDraggingOver.value = false;

    if (!isUserUploadsTab.value || !currentFolder.value) return;

    if (isStorageFull.value) {
        error('Storage limit reached.', { title: 'Storage Full' });
        return;
    }

    const files = event.dataTransfer?.files;

    if (files && files.length) {
        const mockTarget = {
            files: files,
            value: '',
        } as unknown as HTMLInputElement;

        await handleFileUploadFromEvent({ target: mockTarget } as unknown as Event);
    }
};

const toggleViewMode = (mode: ViewMode) => {
    viewMode.value = mode;
    localStorage.setItem('meridian-file-view-mode', mode);
    if (mode !== 'list') {
        loadImagePreviews(items.value);
    }
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
    if (item.type === 'folder' && isUserUploadsTab.value) {
        handleNavigate(item);
    } else {
        handleSelect(item);
    }
};

const handleContextSelect = (item: FileSystemObject) => {
    closeContextMenu();
    handleSelect(item);
};

const handleContextRename = (item: FileSystemObject) => {
    closeContextMenu();
    renamingItem.value = item;
    renameInput.value = item.name;
    isRenaming.value = true;
};

const submitRename = async () => {
    if (!renamingItem.value || !renameInput.value.trim()) return;
    if (renameInput.value.trim() === renamingItem.value.name) {
        isRenaming.value = false;
        return;
    }

    try {
        const updatedItem = await renameFileSystemObject(
            renamingItem.value.id,
            renameInput.value.trim(),
        );
        // Update local state
        const index = items.value.findIndex((i) => i.id === updatedItem.id);
        if (index !== -1) {
            items.value[index] = updatedItem;
        }
        success(`Renamed to "${updatedItem.name}"`);
    } catch (e) {
        console.error(e);
        error('Failed to rename item.');
    } finally {
        isRenaming.value = false;
        renamingItem.value = null;
        renameInput.value = '';
    }
};

const handleContextDownload = async (item: FileSystemObject) => {
    closeContextMenu();
    if (item.type !== 'file') return;

    try {
        const blob = await getFileBlob(item.id);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = item.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (e) {
        console.error(e);
        error('Failed to download file.');
    }
};

const handleContextDelete = (item: FileSystemObject) => {
    closeContextMenu();
    handleDeleteItem(item);
};

// --- Lifecycle Hooks ---
onMounted(initialize);

onUnmounted(() => {
    Object.values(imagePreviews.value).forEach((url) => URL.revokeObjectURL(url));
});
</script>

<template>
    <div class="flex h-full w-full flex-col gap-4">
        <!-- Context Menu -->
        <UiGraphNodeUtilsFilePromptFileContextMenu
            v-if="showContextMenu && contextMenuItem"
            :position="contextMenuPos"
            :item="contextMenuItem"
            @close="closeContextMenu"
            @open="handleContextOpen"
            @select="handleContextSelect"
            @rename="handleContextRename"
            @download="handleContextDownload"
            @delete="handleContextDelete"
        />

        <!-- Header -->
        <div class="border-stone-gray/20 mb-2 flex items-center justify-start gap-2 border-b pb-4">
            <UiIcon name="MajesticonsAttachment" class="text-soft-silk h-6 w-6" />
            <h2 class="text-soft-silk text-xl font-bold">Select Attachments</h2>
            <!-- Storage Warning -->
            <div
                v-if="isStorageFull"
                class="ml-auto flex items-center gap-2 text-xs font-semibold text-red-400"
            >
                <UiIcon name="MdiAlertCircle" class="h-4 w-4" />
                <span>Storage Full</span>
            </div>
        </div>

        <!-- Rename Modal -->
        <AnimatePresence>
            <motion.div
                v-if="isRenaming"
                class="bg-obsidian/80 absolute inset-0 z-50 flex items-center justify-center
                    backdrop-blur-sm"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1 }"
                :exit="{ opacity: 0 }"
            >
                <div
                    class="bg-obsidian border-stone-gray/20 flex flex-col gap-4 rounded-xl border
                        p-6 shadow-xl"
                >
                    <h3 class="text-soft-silk/80 text-lg font-semibold">Rename Item</h3>
                    <input
                        v-model="renameInput"
                        type="text"
                        class="bg-obsidian border-stone-gray/20 text-soft-silk
                            focus:border-ember-glow w-64 rounded-lg border px-3 py-2 text-sm
                            focus:outline-none"
                        autoFocus
                        @keyup.enter="submitRename"
                        @keyup.esc="isRenaming = false"
                    />
                    <div class="flex justify-end gap-2">
                        <button
                            class="hover:bg-stone-gray/10 text-stone-gray rounded px-3 py-1.5
                                text-sm"
                            @click="isRenaming = false"
                        >
                            Cancel
                        </button>
                        <button
                            class="bg-ember-glow text-soft-silk rounded px-3 py-1.5 text-sm"
                            @click="submitRename"
                        >
                            Rename
                        </button>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>

        <!-- Main Layout Split -->
        <div class="flex flex-1 gap-4 overflow-hidden">
            <!-- Sidebar -->
            <div class="border-stone-gray/20 flex w-48 shrink-0 flex-col gap-2 border-r pr-4">
                <button
                    class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium
                        transition-colors"
                    :class="
                        activeTab === 'uploads'
                            ? 'bg-ember-glow/10 text-ember-glow'
                            : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
                    "
                    @click="switchTab('uploads')"
                >
                    <UiIcon name="MdiFolderOutline" class="h-5 w-5" />
                    <span>My Files</span>
                </button>
                <button
                    class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium
                        transition-colors"
                    :class="
                        activeTab === 'generated'
                            ? 'bg-ember-glow/10 text-ember-glow'
                            : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
                    "
                    @click="switchTab('generated')"
                >
                    <UiIcon name="MynauiSparklesSolid" class="h-5 w-5" />
                    <span>Generated</span>
                </button>
            </div>

            <!-- Content Area -->
            <div class="flex min-w-0 flex-1 flex-col gap-4">
                <!-- Toolbar / Breadcrumbs -->
                <div class="flex items-center justify-between">
                    <!-- Breadcrumbs (Only for Uploads) -->
                    <div class="flex min-h-[36px] items-center gap-1 text-sm">
                        <template v-if="isUserUploadsTab">
                            <button
                                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk mr-2
                                    flex h-9 w-9 shrink-0 items-center justify-center rounded-lg
                                    transition-colors duration-200 ease-in-out
                                    disabled:cursor-not-allowed disabled:opacity-50"
                                title="Go back"
                                :disabled="breadcrumbs.length <= 1"
                                @click="handleNavigate(breadcrumbs[breadcrumbs.length - 2])"
                            >
                                <UiIcon name="LineMdChevronSmallUp" class="h-5 w-5 -rotate-90" />
                            </button>
                            <span
                                v-for="(part, index) in breadcrumbs"
                                :key="part.id"
                                class="text-stone-gray/60 flex items-center gap-1"
                            >
                                <span v-if="index > 0" class="text-stone-gray/40">/</span>
                                <button
                                    class="hover:text-soft-silk transition-colors"
                                    :disabled="index === breadcrumbs.length - 1"
                                    @click="handleNavigate(part)"
                                >
                                    {{ part.name === '/' ? 'Root' : part.name }}
                                </button>
                            </span>
                        </template>
                        <template v-else>
                            <span class="text-soft-silk font-medium">Generated Images</span>
                        </template>
                    </div>

                    <!-- Search & Controls -->
                    <div class="flex items-center gap-2">
                        <div class="relative w-full max-w-xs">
                            <UiIcon
                                name="MdiMagnify"
                                class="text-stone-gray/60 pointer-events-none absolute top-1/2
                                    left-3 h-4 w-4 -translate-y-1/2"
                            />
                            <input
                                v-model="searchQuery"
                                type="text"
                                :placeholder="
                                    isUserUploadsTab
                                        ? 'Search current folder...'
                                        : 'Search generated images...'
                                "
                                class="bg-obsidian border-stone-gray/20 text-soft-silk
                                    focus:border-ember-glow h-9 w-full rounded-lg border py-2 pr-8
                                    pl-9 text-sm focus:outline-none"
                            />
                            <button
                                v-if="searchQuery"
                                class="text-stone-gray/60 hover:text-soft-silk absolute top-1/2
                                    right-2 flex h-6 w-6 -translate-y-1/2 items-center
                                    justify-center rounded-md transition-colors"
                                @click="searchQuery = ''"
                            >
                                <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                            </button>
                        </div>

                        <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

                        <!-- View Mode Toggles -->
                        <div class="bg-stone-gray/10 flex items-center rounded-lg p-0.5">
                            <button
                                class="flex h-7 w-7 items-center justify-center rounded
                                    transition-all"
                                :class="
                                    viewMode === 'gallery'
                                        ? 'bg-stone-gray/20 text-soft-silk'
                                        : 'text-stone-gray/50 hover:text-stone-gray/80'
                                "
                                title="Gallery View"
                                @click="toggleViewMode('gallery')"
                            >
                                <UiIcon name="MdiViewGridOutline" class="h-4 w-4" />
                            </button>
                            <button
                                class="flex h-7 w-7 items-center justify-center rounded
                                    transition-all"
                                :class="
                                    viewMode === 'grid'
                                        ? 'bg-stone-gray/20 text-soft-silk'
                                        : 'text-stone-gray/50 hover:text-stone-gray/80'
                                "
                                title="Grid View"
                                @click="toggleViewMode('grid')"
                            >
                                <UiIcon name="MdiViewGridCompact" class="h-4 w-4" />
                            </button>

                            <button
                                class="flex h-7 w-7 items-center justify-center rounded
                                    transition-all"
                                :class="
                                    viewMode === 'list'
                                        ? 'bg-stone-gray/20 text-soft-silk'
                                        : 'text-stone-gray/50 hover:text-stone-gray/80'
                                "
                                title="List View"
                                @click="toggleViewMode('list')"
                            >
                                <UiIcon name="MdiViewListOutline" class="h-4 w-4" />
                            </button>
                        </div>

                        <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

                        <!-- Sorting -->
                        <div class="text-stone-gray/60 flex shrink-0 items-center gap-1 text-sm">
                            <span>Sort by:</span>
                            <button
                                class="rounded px-2 py-0.5 font-medium transition-colors"
                                :class="
                                    sortBy === 'name'
                                        ? 'text-soft-silk bg-stone-gray/20'
                                        : 'hover:bg-stone-gray/10'
                                "
                                @click="sortBy = 'name'"
                            >
                                Name
                            </button>
                            <button
                                class="rounded px-2 py-0.5 font-medium transition-colors"
                                :class="
                                    sortBy === 'date'
                                        ? 'text-soft-silk bg-stone-gray/20'
                                        : 'hover:bg-stone-gray/10'
                                "
                                @click="sortBy = 'date'"
                            >
                                Date
                            </button>
                            <button
                                class="hover:bg-stone-gray/10 rounded p-1 transition-colors"
                                title="Toggle sort direction"
                                @click="sortDirection = sortDirection === 'asc' ? 'desc' : 'asc'"
                            >
                                <UiIcon
                                    :name="'MdiArrowUp'"
                                    class="h-4 w-4 transition-transform duration-200 ease-in-out"
                                    :class="{
                                        'rotate-180': sortDirection === 'desc',
                                    }"
                                />
                            </button>
                        </div>

                        <!-- Upload/Folder Controls (Only in Uploads tab) -->
                        <template v-if="isUserUploadsTab">
                            <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

                            <AnimatePresence>
                                <motion.div
                                    v-if="isCreatingFolder"
                                    :initial="{ width: 0, opacity: 0 }"
                                    :animate="{ width: 'auto', opacity: 1 }"
                                    :exit="{ width: 0, opacity: 0 }"
                                    class="shrink-0 overflow-hidden"
                                >
                                    <input
                                        v-model="newFolderName"
                                        type="text"
                                        placeholder="Folder name..."
                                        class="bg-obsidian border-stone-gray/20 text-soft-silk
                                            focus:border-ember-glow h-9 w-48 rounded-lg border px-3
                                            text-sm focus:outline-none"
                                        @keyup.enter="handleCreateFolder"
                                        @keyup.esc="isCreatingFolder = false"
                                    />
                                </motion.div>
                            </AnimatePresence>
                            <button
                                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex
                                    h-9 w-9 shrink-0 items-center justify-center rounded-lg
                                    transition-colors"
                                title="New Folder"
                                @click="isCreatingFolder = !isCreatingFolder"
                            >
                                <UiIcon name="MdiFolderPlusOutline" class="h-5 w-5" />
                            </button>
                            <button
                                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex
                                    h-9 w-9 shrink-0 items-center justify-center rounded-lg
                                    transition-colors disabled:cursor-not-allowed
                                    disabled:opacity-50"
                                title="Upload Folder"
                                :disabled="isStorageFull"
                                @click="triggerFolderUpload"
                            >
                                <UiIcon name="MdiFolderUploadOutline" class="h-5 w-5" />
                                <input
                                    ref="uploadFolderInputRef"
                                    type="file"
                                    multiple
                                    webkitdirectory
                                    directory
                                    class="hidden"
                                    @change="handleFileUploadFromEvent"
                                />
                            </button>
                            <button
                                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex
                                    h-9 w-9 shrink-0 items-center justify-center rounded-lg
                                    transition-colors disabled:cursor-not-allowed
                                    disabled:opacity-50"
                                title="Upload File"
                                :disabled="isStorageFull"
                                @click="triggerUpload"
                            >
                                <UiIcon name="UilUpload" class="h-5 w-5" />
                                <input
                                    ref="uploadInputRef"
                                    type="file"
                                    class="hidden"
                                    @change="handleFileUploadFromEvent"
                                />
                            </button>
                        </template>
                    </div>
                </div>

                <!-- File Content Area -->
                <div
                    class="bg-obsidian/50 border-stone-gray/20 dark-scrollbar relative flex-grow
                        overflow-y-auto rounded-lg border p-4"
                    @dragover.prevent="isDraggingOver = true"
                    @dragleave.prevent="isDraggingOver = false"
                    @drop.prevent="handleFileDrop"
                >
                    <div
                        v-if="isDraggingOver && isUserUploadsTab"
                        class="border-soft-silk/50 text-soft-silk/70 pointer-events-none absolute
                            inset-0 z-50 flex flex-col items-center justify-center gap-2 rounded-lg
                            border-2 border-dashed text-center backdrop-blur transition-all
                            duration-200 ease-in-out"
                        :class="isStorageFull ? '!border-red-500/50 !text-red-400' : ''"
                    >
                        <UiIcon
                            :name="isStorageFull ? 'MdiCancel' : 'UilUpload'"
                            class="mx-auto mb-2 h-10 w-10"
                        />
                        <p v-if="!isStorageFull">Drop files here to upload</p>
                        <p v-else>Storage Full</p>
                    </div>

                    <div
                        v-if="isLoading"
                        class="text-soft-silk/50 flex h-full items-center justify-center"
                    >
                        Loading...
                    </div>

                    <template v-else-if="filteredAndSortedItems.length > 0">
                        <!-- Grid / Gallery View -->
                        <div
                            v-if="viewMode === 'grid' || viewMode === 'gallery'"
                            class="grid gap-4"
                            :class="
                                viewMode === 'gallery'
                                    ? 'grid-cols-[repeat(auto-fill,minmax(16rem,1fr))]'
                                    : 'grid-cols-[repeat(auto-fill,minmax(8rem,1fr))]'
                            "
                        >
                            <UiGraphNodeUtilsFilePromptFileItem
                                v-for="item in filteredAndSortedItems"
                                :key="item.id"
                                :item="item"
                                :is-selected="isSelected(item)"
                                :has-selected-descendants="hasSelectedDescendants(item)"
                                :preview-url="imagePreviews[item.id]"
                                :view-mode="viewMode === 'gallery' ? 'gallery' : 'grid'"
                                @navigate="handleNavigate"
                                @select="handleSelect"
                                @select-folder-contents="handleSelectFolderContents"
                                @contextmenu="handleContextMenu"
                            />
                        </div>

                        <!-- List View -->
                        <div v-else class="flex h-full flex-col">
                            <!-- List Headers -->
                            <div
                                class="text-stone-gray/60 border-stone-gray/20 mb-2 grid
                                    grid-cols-[1fr_8rem_8rem_10rem] gap-4 border-b px-3 py-2 text-xs
                                    font-medium tracking-wider uppercase"
                            >
                                <div>Name</div>
                                <div>Size</div>
                                <div>Type</div>
                                <div>Date Modified</div>
                            </div>

                            <div class="flex flex-col gap-1 pb-4">
                                <UiGraphNodeUtilsFilePromptFileListItem
                                    v-for="item in filteredAndSortedItems"
                                    :key="item.id"
                                    :item="item"
                                    :is-selected="isSelected(item)"
                                    :has-selected-descendants="hasSelectedDescendants(item)"
                                    @navigate="handleNavigate"
                                    @select="handleSelect"
                                    @select-folder-contents="handleSelectFolderContents"
                                    @contextmenu="handleContextMenu"
                                />
                            </div>
                        </div>
                    </template>

                    <div v-else class="pointer-events-none flex h-full items-center justify-center">
                        <p v-if="searchQuery" class="text-stone-gray/50">
                            'No items match your search.'
                        </p>
                        <p v-else class="text-center">
                            <span v-if="isUserUploadsTab">
                                <span class="text-stone-gray/50">This folder is empty.</span> <br />
                                <span class="text-stone-gray/25"
                                    >Use the buttons above to create a new folder or upload files,
                                    <br />
                                    or drag and drop files here to upload them.</span
                                >
                            </span>
                            <span v-else>
                                <span class="text-stone-gray/50">No generated images found.</span>
                            </span>
                        </p>
                    </div>
                </div>

                <!-- Actions -->
                <div class="mt-auto flex justify-end gap-3 pt-2">
                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk cursor-pointer
                            rounded-lg px-4 py-2 transition-colors duration-200 ease-in-out"
                        @click="$emit('close', initialSelectedFiles)"
                    >
                        Cancel
                    </button>
                    <button
                        class="bg-ember-glow text-soft-silk cursor-pointer rounded-lg px-4 py-2
                            transition-colors duration-200 ease-in-out hover:brightness-90"
                        @click="confirmSelection"
                    >
                        Confirm Selection ({{ selectedFiles.size }})
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
