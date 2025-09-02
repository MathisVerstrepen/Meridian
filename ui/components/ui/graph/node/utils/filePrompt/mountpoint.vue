<script lang="ts" setup>
import { motion } from 'motion-v';

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Local State ---
const isOpen = ref(false);
const activeNodeId = ref<string | null>(null);
const initialSelectedFiles = ref<FileSystemObject[]>([]);

// --- Core Logic Functions ---
const closeFullscreen = (finalSelection?: FileSystemObject[]) => {
    console.log(finalSelection)
    graphEvents.emit('close-attachment-select', {
        selectedFiles: finalSelection || initialSelectedFiles.value,
        nodeId: activeNodeId.value || '',
    });

    isOpen.value = false;
    activeNodeId.value = null;
    initialSelectedFiles.value = [];
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isOpen.value) {
        closeFullscreen(initialSelectedFiles.value);
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('open-attachment-select', async (payload) => {
        isOpen.value = true;
        activeNodeId.value = payload.nodeId;
        initialSelectedFiles.value = payload.selectedFiles || [];
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
            id="attachment-select-mountpoint"
            key="attachment-select-mountpoint"
            :initial="{ opacity: 0, scale: 0.85 }"
            :animate="{ opacity: 1, scale: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
            :exit="{ opacity: 0, scale: 0.85, transition: { duration: 0.15, ease: 'easeIn' } }"
            class="bg-obsidian/90 border-stone-gray/10 absolute top-1/2 left-1/2 z-50 mx-auto flex h-[95%] w-[95%]
                -translate-x-1/2 -translate-y-1/2 cursor-default overflow-hidden rounded-2xl border-2 p-8
                shadow-lg backdrop-blur-md"
        >
            <button
                class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2.5 right-2.5 z-50 flex h-10 w-10 items-center
                    justify-center justify-self-end rounded-full backdrop-blur-sm transition-colors duration-200
                    ease-in-out hover:cursor-pointer"
                aria-label="Close Fullscreen"
                title="Close Fullscreen"
                @click="closeFullscreen(initialSelectedFiles)"
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>

            <UiGraphNodeUtilsFilePromptFileManager
                v-if="isOpen"
                :initial-selected-files="initialSelectedFiles"
                @close="closeFullscreen($event)"
            />
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
