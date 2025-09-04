<script lang="ts" setup>
import { AnimatePresence, motion } from 'motion-v';

interface FileSystemObject {
    id: string;
    name: string;
    type: 'file' | 'folder';
    size?: number;
    content_type?: string;
    created_at: string;
    updated_at: string;
}

// --- Props & Emits ---
const props = defineProps<{
    initialSelectedFiles?: FileSystemObject[];
}>();
const emit = defineEmits(['close']);

// --- Composables ---
const { getRootFolder, getFolderContents, createFolder, uploadFile, deleteFileSystemObject } =
    useAPI();
const { success, error } = useToast();

// --- State ---
const currentFolder = ref<FileSystemObject | null>(null);
const items = ref<FileSystemObject[]>([]);
const breadcrumbs = ref<FileSystemObject[]>([]);
const selectedFiles = ref<Set<FileSystemObject>>(
    new Set(props.initialSelectedFiles?.map((f) => ({ ...f })) || []),
);
const isLoading = ref(true);
const isCreatingFolder = ref(false);
const newFolderName = ref('');
const uploadInputRef = ref<HTMLInputElement | null>(null);
const searchQuery = ref('');
const sortBy = ref<'name' | 'date'>('name');
const sortDirection = ref<'asc' | 'desc'>('asc');
const isDraggingOver = ref(false);

// --- Computed ---
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

// --- Methods ---
const loadFolder = async (folder: FileSystemObject) => {
    if (!folder) return;
    isLoading.value = true;
    searchQuery.value = '';
    try {
        currentFolder.value = folder;
        const contents = await getFolderContents(folder.id);
        items.value = contents;
    } catch (e) {
        console.error(e);
        error('Failed to load folder contents.');
    } finally {
        isLoading.value = false;
    }
};

const initialize = async () => {
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

const isSelected = (item: FileSystemObject) => {
    return [...selectedFiles.value].some((f) => f.id === item.id);
};

const confirmSelection = () => {
    emit('close', Array.from(selectedFiles.value));
};

const handleCreateFolder = async () => {
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
    uploadInputRef.value?.click();
};

const handleFileUpload = async (file: File, parentId: string) => {
    try {
        const newFile = await uploadFile(file, parentId);
        items.value.push(newFile);
        success(`File "${newFile.name}" uploaded.`);
    } catch (e) {
        console.error(e);
        error('Failed to upload file.');
    }
};

const handleFileUploadFromEvent = async (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (!target.files || target.files.length === 0 || !currentFolder.value) return;

    const file = target.files[0];
    await handleFileUpload(file, currentFolder.value.id);

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
    } catch (err) {
        error(`Failed to delete "${itemToDelete.name}".`);
        console.error(err);
    }
};

const handleFileDrop = async (event: DragEvent) => {
    isDraggingOver.value = false;
    const files = event.dataTransfer?.files;

    if (files && files.length) {
        for (let i = 0; i < files.length; i++) {
            await handleFileUpload(files[i], currentFolder.value!.id);
        }
    }
};

// --- Lifecycle Hooks ---
onMounted(initialize);
</script>

<template>
    <div class="flex h-full w-full flex-col gap-4">
        <!-- Header -->
        <div class="border-stone-gray/20 mb-4 flex items-center justify-start gap-2 border-b pb-4">
            <UiIcon name="MajesticonsAttachment" class="text-soft-silk h-6 w-6" />
            <h2 class="text-soft-silk text-xl font-bold">Select Attachments</h2>
        </div>

        <!-- Breadcrumbs & Actions -->
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-1 text-sm">
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk mr-2 flex h-9 w-9 shrink-0 items-center
                        justify-center rounded-lg transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                        disabled:opacity-50"
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
            </div>
            <div class="flex items-center gap-2">
                <div class="relative w-full max-w-xs">
                    <UiIcon
                        name="MdiMagnify"
                        class="text-stone-gray/60 pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
                    />
                    <input
                        v-model="searchQuery"
                        type="text"
                        placeholder="Search current folder..."
                        class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow h-9 w-full rounded-lg border
                            py-2 pr-8 pl-9 text-sm focus:outline-none"
                    />
                    <button
                        v-if="searchQuery"
                        class="text-stone-gray/60 hover:text-soft-silk absolute top-1/2 right-2 flex h-6 w-6 -translate-y-1/2
                            items-center justify-center rounded-md transition-colors"
                        @click="searchQuery = ''"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                    </button>
                </div>

                <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

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
                            class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow h-9 w-48 rounded-lg border
                                px-3 text-sm focus:outline-none"
                            @keyup.enter="handleCreateFolder"
                            @keyup.esc="isCreatingFolder = false"
                        />
                    </motion.div>
                </AnimatePresence>
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9 shrink-0 items-center
                        justify-center rounded-lg transition-colors"
                    title="New Folder"
                    @click="isCreatingFolder = !isCreatingFolder"
                >
                    <UiIcon name="MdiFolderPlusOutline" class="h-5 w-5" />
                </button>
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9 shrink-0 items-center
                        justify-center rounded-lg transition-colors"
                    title="Upload File"
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
            </div>
        </div>

        <!-- File Grid -->
        <div
            class="bg-obsidian/50 border-stone-gray/20 dark-scrollbar relative flex-grow overflow-y-auto rounded-lg
                border p-4"
            @dragover.prevent="isDraggingOver = true"
            @dragleave.prevent="isDraggingOver = false"
            @drop.prevent="handleFileDrop"
        >
            <div
                v-if="isDraggingOver"
                class="border-soft-silk/50 text-soft-silk/70 pointer-events-none absolute inset-0 z-50 flex flex-col
                    items-center justify-center gap-2 rounded-lg border-2 border-dashed text-center backdrop-blur
                    transition-all duration-200 ease-in-out"
            >
                <UiIcon name="UilUpload" class="mx-auto mb-2 h-10 w-10" />
                <p>Drop files here to upload</p>
            </div>

            <div v-if="isLoading" class="flex h-full items-center justify-center">Loading...</div>
            <div
                v-else-if="filteredAndSortedItems.length > 0"
                class="grid grid-cols-[repeat(auto-fill,minmax(8rem,1fr))] gap-4"
            >
                <UiGraphNodeUtilsFilePromptFileItem
                    v-for="item in filteredAndSortedItems"
                    :key="item.id"
                    :item="item"
                    :is-selected="isSelected(item)"
                    @navigate="handleNavigate"
                    @select="handleSelect"
                    @delete="handleDeleteItem"
                />
            </div>
            <div v-else class="flex h-full items-center justify-center pointer-events-none">
                <p v-if="searchQuery" class="text-stone-gray/50">'No items match your search.'</p>
                <p v-else class="text-center">
                    <span class="text-stone-gray/50">This folder is empty.</span> <br />
                    <span class="text-stone-gray/25"
                        >Use the buttons above to create a new folder or upload files, <br />
                        or drag and drop files here to upload them.</span
                    >
                </p>
            </div>
        </div>

        <!-- Actions -->
        <div class="mt-auto flex justify-end gap-3 pt-4">
            <button
                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk cursor-pointer rounded-lg px-4 py-2
                    transition-colors duration-200 ease-in-out"
                @click="$emit('close', initialSelectedFiles)"
            >
                Cancel
            </button>
            <button
                class="bg-ember-glow text-soft-silk cursor-pointer rounded-lg px-4 py-2 transition-colors duration-200
                    ease-in-out hover:brightness-90"
                @click="confirmSelection"
            >
                Confirm Selection ({{ selectedFiles.size }})
            </button>
        </div>
    </div>
</template>
