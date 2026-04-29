<script lang="ts" setup>
import '@/assets/css/image-playground.css';

definePageMeta({ layout: 'blank', middleware: 'auth' });
useHead({ title: 'Meridian — Image Atelier' });

type ComposePaneExpose = {
    focusPrompt: () => void;
    handleFiles: (files: FileList | File[] | null) => Promise<void>;
};

const composePaneRef = ref<ComposePaneExpose | null>(null);
const isPageDragging = ref(false);
let pageDragDepth = 0;

const forwardFilesToComposePane = (files: FileList | File[] | null) => {
    void composePaneRef.value?.handleFiles(files);
};

const focusPrompt = () => {
    nextTick(() => composePaneRef.value?.focusPrompt());
};

const onPagePaste = (event: ClipboardEvent) => {
    const items = event.clipboardData?.items;
    if (!items) return;
    const files = Array.from(items)
        .filter((item) => item.kind === 'file')
        .map((item) => item.getAsFile())
        .filter((file): file is File => Boolean(file && file.type.startsWith('image/')));

    if (!files.length) return;
    event.preventDefault();
    forwardFilesToComposePane(files);
};

const onPageDragEnter = (event: DragEvent) => {
    if (!event.dataTransfer?.types.includes('Files')) return;
    pageDragDepth += 1;
    isPageDragging.value = true;
};

const onPageDragLeave = () => {
    pageDragDepth = Math.max(0, pageDragDepth - 1);
    if (pageDragDepth === 0) isPageDragging.value = false;
};

const onPageDrop = (event: DragEvent) => {
    pageDragDepth = 0;
    isPageDragging.value = false;
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    event.preventDefault();
    forwardFilesToComposePane(files);
};

const onPageDragOver = (event: DragEvent) => {
    if (event.dataTransfer?.types.includes('Files')) {
        event.preventDefault();
    }
};
</script>

<template>
    <div
        class="darkroom bg-obsidian text-soft-silk relative h-full w-full overflow-hidden"
        @dragenter="onPageDragEnter"
        @dragleave="onPageDragLeave"
        @dragover="onPageDragOver"
        @drop="onPageDrop"
        @paste="onPagePaste"
    >
        <svg
            class="pointer-events-none absolute inset-0 z-0 h-full w-full opacity-[0.13]"
            aria-hidden="true"
        >
            <pattern id="darkroom-dots" patternUnits="userSpaceOnUse" width="28" height="28">
                <circle cx="14" cy="14" r="1" fill="var(--color-soft-silk)" />
            </pattern>
            <rect width="100%" height="100%" :fill="`url(#darkroom-dots)`" />
        </svg>
        <div class="darkroom-glow pointer-events-none absolute inset-0 z-0" aria-hidden="true" />
        <div class="darkroom-grain pointer-events-none absolute inset-0 z-0" aria-hidden="true" />

        <UiImagesPlaygroundDragOverlay :visible="isPageDragging" />
        <UiGraphNodeUtilsFilePromptMountpoint />

        <div class="relative z-10 flex h-full flex-col px-4 pt-4 pb-3 lg:px-6 lg:pt-6">
            <UiImagesPlaygroundHeader />

            <main
                class="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[440px_1fr]
                    xl:grid-cols-[470px_1fr] 2xl:grid-cols-[500px_1fr]"
            >
                <UiImagesPlaygroundComposePane ref="composePaneRef" />
                <UiImagesPlaygroundGalleryPane @reuse="focusPrompt" />
            </main>
        </div>
    </div>
</template>
