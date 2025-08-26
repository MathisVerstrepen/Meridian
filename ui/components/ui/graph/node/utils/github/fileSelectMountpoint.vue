<script lang="ts" setup>
import { motion } from 'motion-v';
import type { RepoContent, FileTreeNode } from '@/types/github';

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Local State ---
const isOpen = ref(false);
const repoContent = ref<RepoContent | null>(null);
const selectedFiles = ref<FileTreeNode[]>([]);

// --- Core Logic Functions ---
const closeFullscreen = (finalSelection?: FileTreeNode[]) => {
    graphEvents.emit('close-github-file-select', { selectedFilePaths: finalSelection || [] });

    repoContent.value = null;
    isOpen.value = false;
    selectedFiles.value = [];
};

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('open-github-file-select', async (repoContentData) => {
        isOpen.value = true;
        repoContent.value = repoContentData.repoContent;
        selectedFiles.value = repoContentData.repoContent.selectedFiles || [];
    });

    onUnmounted(unsubscribe);
});
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-show="isOpen"
            id="github-file-select-mountpoint"
            key="github-file-select-mountpoint"
            :initial="{ opacity: 0, scale: 0.85 }"
            :animate="{ opacity: 1, scale: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
            :exit="{ opacity: 0, scale: 0.85, transition: { duration: 0.15, ease: 'easeIn' } }"
            class="bg-obsidian/90 border-stone-gray/10 absolute top-1/2 left-1/2 z-50 mx-auto flex h-[95%] w-[95%]
                -translate-x-1/2 -translate-y-1/2 cursor-grab overflow-hidden rounded-2xl border-2 px-4 py-8
                shadow-lg backdrop-blur-md"
        >
            <button
                class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-4 right-4 z-50 flex h-10 w-10 items-center
                    justify-center justify-self-end rounded-full backdrop-blur-sm transition-colors duration-200
                    ease-in-out hover:cursor-pointer"
                @click="closeFullscreen()"
                aria-label="Close Fullscreen"
                title="Close Fullscreen"
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>

            <UiGraphNodeUtilsGithubFileTreeSelector
                v-if="repoContent"
                :tree-data="repoContent.files"
                :initial-selected-paths="selectedFiles"
                :repo="repoContent.repo"
                @update:selectedFiles="selectedFiles = $event"
                @close="closeFullscreen"
            ></UiGraphNodeUtilsGithubFileTreeSelector>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
