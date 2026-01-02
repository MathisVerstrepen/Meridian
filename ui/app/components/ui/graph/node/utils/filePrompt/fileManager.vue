<script lang="ts" setup>
// --- Props & Emits ---
const props = defineProps<{
    initialSelectedFiles?: FileSystemObject[];
}>();
const emit = defineEmits(['close']);

// --- Composables ---
const {
    activeTab,
    currentFolder,
    items,
    breadcrumbs,
    isLoading,
    imagePreviews,
    isUserUploadsTab,
    switchTab,
    handleNavigate,
    initialize,
    loadImagePreviews,
} = useFileBrowser();

const { searchQuery, sortBy, sortDirection, viewMode, toggleViewMode, filteredAndSortedItems } =
    useFileFiltering(items);

const {
    selectedFiles,
    handleSelect,
    handleSelectFolderContents,
    isSelected,
    hasSelectedDescendants,
} = useFileSelection(props.initialSelectedFiles);

const {
    isCreatingFolder,
    newFolderName,
    isRenaming,
    renamingItem,
    renameInput,
    isDraggingOver,
    isStorageFull,
    handleCreateFolder,
    handleFileUploadFromEvent,
    handleDeleteItem,
    submitRename,
    handleDownload,
} = useFileOperations(items, currentFolder, isUserUploadsTab, (files) =>
    loadImagePreviews(files, viewMode.value),
);

// --- Local State for Context Menu ---
const showContextMenu = ref(false);
const contextMenuPos = ref({ x: 0, y: 0 });
const contextMenuItem = ref<FileSystemObject | null>(null);
const uploadInputRef = ref<HTMLInputElement | null>(null);
const uploadFolderInputRef = ref<HTMLInputElement | null>(null);

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
        handleNavigate(item, viewMode.value);
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

const handleContextDelete = (item: FileSystemObject) => {
    closeContextMenu();
    handleDeleteItem(item, selectedFiles.value);
};

const handleContextDownload = (item: FileSystemObject) => {
    closeContextMenu();
    handleDownload(item);
};

// --- Drag & Drop ---
const handleFileDrop = async (event: DragEvent) => {
    isDraggingOver.value = false;
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
onMounted(() => initialize(viewMode.value));

const confirmSelection = () => {
    emit('close', Array.from(selectedFiles.value));
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
            <div
                v-if="isStorageFull"
                class="ml-auto flex items-center gap-2 text-xs font-semibold text-red-400"
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
                @switch-tab="switchTab($event, viewMode)"
            />

            <!-- Content Area -->
            <div class="flex min-w-0 flex-1 flex-col gap-4">
                <!-- Toolbar -->
                <UiGraphNodeUtilsFilePromptFileManagerToolbar
                    v-model:search-query="searchQuery"
                    v-model:sort-by="sortBy"
                    v-model:sort-direction="sortDirection"
                    v-model:is-creating-folder="isCreatingFolder"
                    v-model:new-folder-name="newFolderName"
                    :breadcrumbs="breadcrumbs"
                    :view-mode="viewMode"
                    :is-user-uploads-tab="isUserUploadsTab"
                    :is-storage-full="isStorageFull"
                    @navigate="handleNavigate($event, viewMode)"
                    @toggle-view-mode="toggleViewMode"
                    @create-folder="handleCreateFolder"
                    @trigger-upload="triggerUpload"
                    @trigger-folder-upload="triggerFolderUpload"
                />

                <!-- File Grid/List -->
                <div
                    class="bg-obsidian/50 border-stone-gray/20 dark-scrollbar relative flex-grow
                        overflow-y-auto rounded-lg border p-4"
                    @dragover.prevent="isDraggingOver = true"
                    @dragleave.prevent="isDraggingOver = false"
                    @drop.prevent="handleFileDrop"
                >
                    <!-- Drag Overlay -->
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

                    <!-- Loading -->
                    <div
                        v-if="isLoading"
                        class="text-soft-silk/50 flex h-full items-center justify-center"
                    >
                        Loading...
                    </div>

                    <!-- Content -->
                    <template v-else-if="filteredAndSortedItems.length > 0">
                        <!-- Grid / Gallery -->
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
                                @navigate="handleNavigate($event, viewMode)"
                                @select="handleSelect"
                                @select-folder-contents="handleSelectFolderContents"
                                @contextmenu="handleContextMenu"
                            />
                        </div>

                        <!-- List -->
                        <div v-else class="flex h-full flex-col">
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
                                    @navigate="handleNavigate($event, viewMode)"
                                    @select="handleSelect"
                                    @select-folder-contents="handleSelectFolderContents"
                                    @contextmenu="handleContextMenu"
                                />
                            </div>
                        </div>
                    </template>

                    <!-- Empty State -->
                    <div v-else class="pointer-events-none flex h-full items-center justify-center">
                        <p v-if="searchQuery" class="text-stone-gray/50">
                            No items match your search.
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

                <!-- Footer Actions -->
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
