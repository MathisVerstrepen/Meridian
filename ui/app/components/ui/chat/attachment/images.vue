<script lang="ts" setup>
import type { MessageContentImageURL } from '@/types/graph';
import { AnimatePresence, motion } from 'motion-v';

// --- Props ---
const props = defineProps<{
    images: MessageContentImageURL[];
}>();

// --- Composables ---
const { getFileBlob } = useAPI();

// --- State ---
const imageObjectUrls = ref<Record<string, string>>({});
const imageLoadStatus = ref<Record<string, 'loading' | 'loaded' | 'error'>>({});

const isFullscreenOpen = ref(false);
const fullscreenImageUrl = ref<string | null>(null);

// --- Methods ---
const loadImage = async (imageId: string) => {
    if (
        !imageId ||
        imageLoadStatus.value[imageId] === 'loaded' ||
        imageLoadStatus.value[imageId] === 'loading'
    ) {
        return;
    }

    imageLoadStatus.value[imageId] = 'loading';

    try {
        const blob = await getFileBlob(imageId);
        imageObjectUrls.value[imageId] = URL.createObjectURL(blob);
        imageLoadStatus.value[imageId] = 'loaded';
    } catch (error) {
        console.error(`Failed to load image with ID ${imageId}:`, error);
        imageLoadStatus.value[imageId] = 'error';
    }
};

const openFullscreen = (url: string) => {
    fullscreenImageUrl.value = url;
    isFullscreenOpen.value = true;
};

const closeFullscreen = () => {
    isFullscreenOpen.value = false;
    // Delay clearing the URL to allow for exit animation
    setTimeout(() => {
        fullscreenImageUrl.value = null;
    }, 200);
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isFullscreenOpen.value) {
        closeFullscreen();
    }
};

// --- Watchers ---
watch(
    () => props.images,
    (newImages) => {
        if (newImages) {
            newImages.forEach((image) => {
                loadImage(image.id);
            });
        }
    },
    { immediate: true, deep: true },
);

watch(isFullscreenOpen, (isOpen) => {
    if (isOpen) {
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', handleKeyDown);
    } else {
        document.body.style.overflow = '';
        document.removeEventListener('keydown', handleKeyDown);
    }
});

// --- Lifecycle ---
onUnmounted(() => {
    Object.values(imageObjectUrls.value).forEach((url) => {
        if (url) {
            URL.revokeObjectURL(url);
        }
    });
    document.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
    <ul class="decoration-none flex w-fit list-none flex-wrap gap-2">
        <li
            v-for="(imageUrl, index) in images"
            :key="index"
            class="group text-soft-silk/70 border-stone-gray/30 bg-obsidian relative flex h-[88px] w-[88px]
                items-center justify-center rounded-xl border p-1 text-sm font-bold transition-colors duration-200"
        >
            <template v-if="imageLoadStatus[imageUrl.id] === 'loaded'">
                <NuxtImg
                    :src="imageObjectUrls[imageUrl.id]"
                    class="h-20 w-20 rounded-lg object-cover"
                    height="80"
                    width="80"
                    loading="lazy"
                />
                <div
                    class="absolute flex h-full w-full cursor-pointer items-center justify-center rounded-lg bg-black/60
                        opacity-0 backdrop-blur-[1px] transition-opacity duration-200 group-hover:opacity-100"
                    @click="openFullscreen(imageObjectUrls[imageUrl.id])"
                >
                    <UiIcon name="MdiFullscreen" class="h-6 w-6 text-white" />
                </div>
            </template>
            <template v-else-if="imageLoadStatus[imageUrl.id] === 'loading'"> </template>
            <template v-else>
                <UiIcon name="PhImageBroken" class="h-6 w-6 text-red-400/50" />
            </template>
        </li>
    </ul>

    <!-- Fullscreen Modal -->
    <Teleport to="body">
        <AnimatePresence>
            <motion.div
                v-if="isFullscreenOpen && fullscreenImageUrl"
                class="fixed inset-0 z-[100] flex cursor-zoom-out items-center justify-center bg-black/80 backdrop-blur-sm"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1 }"
                :exit="{ opacity: 0 }"
                @click="closeFullscreen"
            >
                <motion.img
                    :key="fullscreenImageUrl"
                    :src="fullscreenImageUrl"
                    class="max-h-[90vh] max-w-[90vw] cursor-default object-contain"
                    :initial="{ scale: 0.8, opacity: 0 }"
                    :animate="{
                        scale: 1,
                        opacity: 1,
                        transition: { duration: 0.2, ease: 'easeOut' },
                    }"
                    :exit="{
                        scale: 0.8,
                        opacity: 0,
                        transition: { duration: 0.15, ease: 'easeIn' },
                    }"
                    @click.stop
                />
                <button
                    class="absolute top-4 right-4 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full
                        bg-white/10 text-white transition-colors hover:bg-white/20"
                    aria-label="Close fullscreen"
                    @click.stop="closeFullscreen"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-6 w-6" />
                </button>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>

<style scoped></style>
