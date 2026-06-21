<script lang="ts" setup>
const props = defineProps<{
    isOpen: boolean;
    title: string;
    submitLabel: string;
}>();

const emit = defineEmits<{
    (e: 'close'): void;
    (e: 'submit', folder: FileSystemObject): void;
}>();

const { getRootFolder, getFolderContents } = useAPI();
const { error } = useToast();

const currentFolder = ref<FileSystemObject | null>(null);
const breadcrumbs = ref<FileSystemObject[]>([]);
const folders = ref<FileSystemObject[]>([]);
const isLoading = ref(false);

const loadFolder = async (folder: FileSystemObject) => {
    isLoading.value = true;
    try {
        currentFolder.value = folder;
        folders.value = (await getFolderContents(folder.id)).filter((item) => item.type === 'folder');
    } catch (e) {
        console.error(e);
        error('Failed to load folders.');
    } finally {
        isLoading.value = false;
    }
};

const navigateToFolder = async (folder: FileSystemObject) => {
    const breadcrumbIndex = breadcrumbs.value.findIndex((item) => item.id === folder.id);
    if (breadcrumbIndex > -1) {
        breadcrumbs.value = breadcrumbs.value.slice(0, breadcrumbIndex + 1);
    } else {
        breadcrumbs.value.push(folder);
    }
    await loadFolder(folder);
};

watch(
    () => props.isOpen,
    async (isOpen) => {
        if (!isOpen) return;

        try {
            const rootFolder = await getRootFolder();
            breadcrumbs.value = [rootFolder];
            await loadFolder(rootFolder);
        } catch (e) {
            console.error(e);
            error('Failed to load root folder.');
        }
    },
);
</script>

<template>
    <div
        v-if="isOpen"
        class="fixed inset-0 z-100 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        @click.self="emit('close')"
    >
        <div class="bg-obsidian border-stone-gray/20 flex w-full max-w-lg flex-col rounded-2xl border p-5 shadow-xl">
            <div class="mb-4 flex items-center justify-between gap-4">
                <div>
                    <h3 class="text-soft-silk text-lg font-semibold">{{ title }}</h3>
                    <p class="text-stone-gray/60 text-sm">Choose the destination folder.</p>
                </div>
                <button
                    class="text-stone-gray/60 hover:text-soft-silk rounded-lg p-1 transition-colors"
                    @click="emit('close')"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                </button>
            </div>

            <div class="border-stone-gray/20 mb-3 flex min-h-9 items-center gap-1 border-b pb-3 text-sm">
                <span
                    v-for="(part, index) in breadcrumbs"
                    :key="part.id"
                    class="text-stone-gray/60 flex items-center gap-1"
                >
                    <span v-if="index > 0" class="text-stone-gray/40">/</span>
                    <button
                        class="hover:text-soft-silk transition-colors"
                        :disabled="index === breadcrumbs.length - 1"
                        @click="navigateToFolder(part)"
                    >
                        {{ part.name === '/' ? 'Root' : part.name }}
                    </button>
                </span>
            </div>

            <div class="dark-scrollbar min-h-48 overflow-y-auto">
                <div v-if="isLoading" class="text-stone-gray/60 flex h-48 items-center justify-center text-sm">
                    Loading folders...
                </div>
                <div v-else-if="folders.length === 0" class="text-stone-gray/50 flex h-48 items-center justify-center text-sm">
                    This folder has no subfolders.
                </div>
                <template v-else>
                    <button
                        v-for="folder in folders"
                        :key="folder.id"
                        class="hover:bg-stone-gray/10 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors"
                        @click="navigateToFolder(folder)"
                    >
                        <UiIcon name="MdiFolderOutline" class="text-stone-gray/70 h-5 w-5" />
                        <span class="text-soft-silk truncate text-sm">{{ folder.name }}</span>
                    </button>
                </template>
            </div>

            <div class="mt-4 flex justify-end gap-3">
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk rounded-lg px-4 py-2 transition-colors"
                    @click="emit('close')"
                >
                    Cancel
                </button>
                <button
                    class="bg-ember-glow text-soft-silk rounded-lg px-4 py-2 transition-colors hover:brightness-90 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="!currentFolder"
                    @click="currentFolder && emit('submit', currentFolder)"
                >
                    {{ submitLabel }} Here
                </button>
            </div>
        </div>
    </div>
</template>
