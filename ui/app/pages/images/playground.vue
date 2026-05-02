<script lang="ts" setup>
import '@/assets/css/image-playground.css';

definePageMeta({ layout: 'blank', middleware: 'auth' });
useHead({ title: 'Meridian — Media Playground' });

type MediaPlaygroundMode = 'image-generation' | 'image-edit' | 'video-generation';

type ComposePaneExpose = {
    focusPrompt: () => void;
    handleFiles: (files: FileList | File[] | null) => Promise<void>;
};

const composePaneRef = ref<ComposePaneExpose | null>(null);
const activeMode = ref<MediaPlaygroundMode>('image-generation');
const isPageDragging = ref(false);
let pageDragDepth = 0;

const forwardFilesToComposePane = (files: FileList | File[] | null) => {
    if (activeMode.value !== 'image-generation') return;
    void composePaneRef.value?.handleFiles(files);
};

const focusPrompt = () => {
    if (activeMode.value !== 'image-generation') return;
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
    if (activeMode.value !== 'image-generation') return;
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
    if (activeMode.value !== 'image-generation') return;
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    event.preventDefault();
    forwardFilesToComposePane(files);
};

const onPageDragOver = (event: DragEvent) => {
    if (activeMode.value !== 'image-generation') return;
    if (event.dataTransfer?.types.includes('Files')) {
        event.preventDefault();
    }
};

const emptyModeCopy = computed(() => {
    if (activeMode.value === 'image-edit') {
        return {
            eyebrow: 'Image Edit',
            title: 'Image edit workspace coming next.',
            body: 'This mode is reserved for canvas edits, reference-guided transforms, and inpainting controls.',
        };
    }

    return {
        eyebrow: 'Video Generation',
        title: 'Video generation workspace coming next.',
        body: 'This mode is reserved for motion prompts, duration controls, and generated video reels.',
    };
});
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

        <UiImagesPlaygroundDragOverlay
            :visible="activeMode === 'image-generation' && isPageDragging"
        />
        <UiGraphNodeUtilsFilePromptMountpoint />

        <div class="relative z-10 flex h-full flex-col px-4 pt-4 pb-3 lg:px-6 lg:pt-6">
            <UiImagesPlaygroundHeader v-model:mode="activeMode" />

            <main
                v-if="activeMode === 'image-generation'"
                class="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[440px_1fr]
                    xl:grid-cols-[470px_1fr] 2xl:grid-cols-[500px_1fr]"
            >
                <UiImagesPlaygroundComposePane ref="composePaneRef" />
                <UiImagesPlaygroundGalleryPane @reuse="focusPrompt" />
            </main>

            <main
                v-else
                class="border-stone-gray/12 bg-obsidian/45 flex min-h-0 flex-1 items-center
                    justify-center rounded-[2rem] border p-6 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
            >
                <div class="max-w-xl">
                    <p class="text-ember-glow text-xs font-semibold tracking-[0.35em] uppercase">
                        {{ emptyModeCopy.eyebrow }}
                    </p>
                    <h2 class="font-outfit text-soft-silk mt-4 text-3xl font-bold tracking-tight">
                        {{ emptyModeCopy.title }}
                    </h2>
                    <p class="text-stone-gray mt-3 text-sm leading-6">
                        {{ emptyModeCopy.body }}
                    </p>
                </div>
            </main>
        </div>
    </div>
</template>
