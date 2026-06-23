<script lang="ts" setup>
import { motion, AnimatePresence } from 'motion-v';

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
    <AnimatePresence>
        <motion.div
            v-if="isOpen"
            class="fixed inset-0 z-100 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            :initial="{ opacity: 0 }"
            :animate="{ opacity: 1 }"
            :exit="{ opacity: 0 }"
            @click.self="emit('close')"
        >
            <motion.div
                class="bg-obsidian border-stone-gray/20 flex w-full max-w-lg flex-col rounded-2xl border p-6
                    shadow-2xl"
                :initial="{ scale: 0.92, opacity: 0 }"
                :animate="{ scale: 1, opacity: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
                :exit="{ scale: 0.92, opacity: 0, transition: { duration: 0.15, ease: 'easeIn' } }"
            >
                <!-- Header -->
                <div class="mb-4 flex items-center justify-between gap-4">
                    <div class="flex items-center gap-3">
                        <div class="bg-ember-glow/10 flex h-10 w-10 items-center justify-center rounded-xl">
                            <UiIcon
                                :name="submitLabel === 'Move' ? 'MdiFolderMoveOutline' : 'MaterialSymbolsContentCopyOutlineRounded'"
                                class="text-ember-glow h-5 w-5"
                            />
                        </div>
                        <div>
                            <h3 class="text-soft-silk text-lg font-semibold">{{ title }}</h3>
                            <p class="text-stone-gray/60 text-sm">Choose the destination folder.</p>
                        </div>
                    </div>
                    <button
                        class="text-stone-gray/60 hover:bg-stone-gray/10 hover:text-soft-silk rounded-lg p-1.5
                            transition-colors"
                        @click="emit('close')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                    </button>
                </div>

                <!-- Breadcrumbs -->
                <div class="border-stone-gray/15 mb-3 flex min-h-9 items-center gap-1 border-b pb-3 text-sm">
                    <UiIcon name="MdiFolderOutline" class="text-stone-gray/50 mr-1 h-4 w-4 shrink-0" />
                    <span
                        v-for="(part, index) in breadcrumbs"
                        :key="part.id"
                        class="text-stone-gray/60 flex items-center gap-1"
                    >
                        <span v-if="index > 0" class="text-stone-gray/30">/</span>
                        <button
                            class="hover:text-soft-silk transition-colors"
                            :class="index === breadcrumbs.length - 1 ? 'text-soft-silk font-medium' : ''"
                            :disabled="index === breadcrumbs.length - 1"
                            @click="navigateToFolder(part)"
                        >
                            {{ part.name === '/' ? 'Root' : part.name }}
                        </button>
                    </span>
                </div>

                <!-- Folder list -->
                <div class="dark-scrollbar min-h-48 max-h-72 overflow-y-auto rounded-xl">
                    <div
                        v-if="isLoading"
                        class="text-stone-gray/60 flex h-48 flex-col items-center justify-center gap-2 text-sm"
                    >
                        <UiIcon name="MaterialSymbolsProgressActivity" class="h-6 w-6 animate-spin" />
                        <span>Loading folders...</span>
                    </div>
                    <div
                        v-else-if="folders.length === 0"
                        class="flex h-48 flex-col items-center justify-center gap-2 text-sm"
                    >
                        <UiIcon name="MdiFolderOutline" class="text-stone-gray/30 h-8 w-8" />
                        <p class="text-stone-gray/50">This folder has no subfolders.</p>
                    </div>
                    <template v-else>
                        <button
                            v-for="folder in folders"
                            :key="folder.id"
                            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 rounded-lg px-3 py-2.5
                                text-left transition-all duration-200"
                            @click="navigateToFolder(folder)"
                        >
                            <UiIcon name="MdiFolderOutline" class="text-stone-gray/70 h-5 w-5 shrink-0" />
                            <span class="text-soft-silk truncate text-sm">{{ folder.name }}</span>
                            <UiIcon name="LineMdChevronSmallUp" class="text-stone-gray/30 ml-auto h-4 w-4 -rotate-90" />
                        </button>
                    </template>
                </div>

                <!-- Actions -->
                <div class="mt-5 flex justify-end gap-3">
                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk rounded-lg px-4 py-2.5
                            text-sm font-medium transition-colors"
                        @click="emit('close')"
                    >
                        Cancel
                    </button>
                    <button
                        class="bg-ember-glow text-obsidian rounded-lg px-4 py-2.5 text-sm font-semibold
                            transition-all hover:brightness-110 disabled:cursor-not-allowed
                            disabled:opacity-40"
                        :disabled="!currentFolder"
                        @click="currentFolder && emit('submit', currentFolder)"
                    >
                        {{ submitLabel }} Here
                    </button>
                </div>
            </motion.div>
        </motion.div>
    </AnimatePresence>
</template>
