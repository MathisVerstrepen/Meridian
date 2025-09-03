<script lang="ts" setup>
import { motion } from 'motion-v';
import type { RepoContent, FileTreeNode } from '@/types/github';

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Local State ---
const isOpen = ref(false);
const repoContent = ref<RepoContent | null>(null);
const selectedFiles = ref<FileTreeNode[]>([]);
const initialSelectedFiles = ref<FileTreeNode[]>([]);
const activeNodeId = ref<string | null>(null);

// --- Core Logic Functions ---
const closeFullscreen = (payload?: { files: FileTreeNode[]; branch: string }) => {
    graphEvents.emit('close-github-file-select', {
        selectedFilePaths: payload ? payload.files : initialSelectedFiles.value,
        nodeId: activeNodeId.value || '',
        branch: payload ? payload.branch : repoContent.value?.currentBranch,
    });

    repoContent.value = null;
    isOpen.value = false;
    selectedFiles.value = [];
    activeNodeId.value = null;
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isOpen.value) {
        closeFullscreen();
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('open-github-file-select', async (payload) => {
        isOpen.value = true;
        repoContent.value = payload.repoContent;
        selectedFiles.value = payload.repoContent.selectedFiles || [];
        activeNodeId.value = payload.nodeId;
        initialSelectedFiles.value = [...selectedFiles.value];
    });

    document.addEventListener('keydown', handleKeyDown);

    onUnmounted(unsubscribe);
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
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
                -translate-x-1/2 -translate-y-1/2 cursor-grab overflow-hidden rounded-2xl border-2 px-8 py-8
                shadow-lg backdrop-blur-md"
        >
            <button
                class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2.5 right-2.5 z-50 flex h-10 w-10 items-center
                    justify-center justify-self-end rounded-full backdrop-blur-sm transition-colors duration-200
                    ease-in-out hover:cursor-pointer"
                aria-label="Close Fullscreen"
                title="Close Fullscreen"
                @click="
                    closeFullscreen(
                        repoContent
                            ? { files: selectedFiles, branch: repoContent.currentBranch }
                            : undefined,
                    )
                "
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>

            <UiGraphNodeUtilsGithubFileTreeSelector
                v-if="repoContent"
                :tree-data="repoContent.files"
                :initial-selected-paths="selectedFiles"
                :repo="repoContent.repo"
                :branches="repoContent.branches"
                :initial-branch="repoContent.currentBranch"
                @update:selected-files="selectedFiles = $event"
                @update:repo-content="repoContent = $event"
                @close="closeFullscreen"
            />
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
