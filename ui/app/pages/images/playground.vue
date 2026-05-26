<script lang="ts" setup>
import '@/assets/css/image-playground.css';

definePageMeta({ layout: 'blank', middleware: 'auth' });
useHead({ title: 'Meridian — Media Playground' });

type MediaPlaygroundMode = 'image-generation' | 'image-edit' | 'video-generation';

type ComposePaneExpose = {
    focusPrompt: () => void;
    handleFiles: (files: FileList | File[] | null) => Promise<void>;
};

type EditPaneExpose = {
    handleFiles: (files: FileList | File[] | null) => void;
};

type VideoPaneExpose = {
    focusPrompt: () => void;
    handleFiles: (files: FileList | File[] | null) => Promise<void>;
};

const route = useRoute();
const router = useRouter();
const composePaneRef = ref<ComposePaneExpose | null>(null);
const editPaneRef = ref<EditPaneExpose | null>(null);
const videoPaneRef = ref<VideoPaneExpose | null>(null);
const playgroundStore = useImagePlaygroundStore();
const { isReorderingSourceImages } = storeToRefs(playgroundStore);
const modeValues: MediaPlaygroundMode[] = ['image-generation', 'image-edit', 'video-generation'];
const isMediaMode = (mode: unknown): mode is MediaPlaygroundMode =>
    typeof mode === 'string' && modeValues.includes(mode as MediaPlaygroundMode);
const modeFromRoute = () => {
    const mode = Array.isArray(route.query.mode) ? route.query.mode[0] : route.query.mode;
    return isMediaMode(mode) ? mode : 'image-generation';
};
const activeMode = ref<MediaPlaygroundMode>(modeFromRoute());
const isPageDragging = ref(false);
let pageDragDepth = 0;

const acceptsPageFiles = computed(() =>
    !isReorderingSourceImages.value &&
    ['image-generation', 'image-edit', 'video-generation'].includes(activeMode.value),
);

const forwardFilesToActivePane = (files: FileList | File[] | null) => {
    if (activeMode.value === 'image-generation') {
        void composePaneRef.value?.handleFiles(files);
        return;
    }
    if (activeMode.value === 'image-edit') {
        editPaneRef.value?.handleFiles(files);
        return;
    }
    if (activeMode.value === 'video-generation') {
        void videoPaneRef.value?.handleFiles(files);
    }
};

const focusPrompt = () => {
    if (activeMode.value === 'image-generation') {
        nextTick(() => composePaneRef.value?.focusPrompt());
        return;
    }
    if (activeMode.value === 'video-generation') {
        nextTick(() => videoPaneRef.value?.focusPrompt());
    }
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
    forwardFilesToActivePane(files);
};

const onPageDragEnter = (event: DragEvent) => {
    if (!acceptsPageFiles.value) return;
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
    if (!acceptsPageFiles.value) return;
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    event.preventDefault();
    forwardFilesToActivePane(files);
};

const onPageDragOver = (event: DragEvent) => {
    if (!acceptsPageFiles.value) return;
    if (event.dataTransfer?.types.includes('Files')) {
        event.preventDefault();
    }
};

watch(
    () => route.query.mode,
    () => {
        const nextMode = modeFromRoute();
        if (nextMode !== activeMode.value) activeMode.value = nextMode;
    },
);

watch(activeMode, (mode) => {
    const currentMode = Array.isArray(route.query.mode) ? route.query.mode[0] : route.query.mode;
    if (currentMode === mode) return;
    void router.replace({
        query: {
            ...route.query,
            mode,
        },
    });
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
            :visible="['image-generation', 'video-generation'].includes(activeMode) && isPageDragging"
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

            <UiImagesPlaygroundEditPane
                v-else-if="activeMode === 'image-edit'"
                ref="editPaneRef"
            />

            <UiImagesPlaygroundVideoPane v-else ref="videoPaneRef" />
        </div>
    </div>
</template>
