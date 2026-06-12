<script lang="ts" setup>
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import {
    imagePlaygroundDownloadName,
    imagePlaygroundDownloadUrl,
    imagePlaygroundFormatBytes,
    imagePlaygroundImageUrl,
    imagePlaygroundModelIcon,
} from '@/utils/imagePlayground';

const playgroundStore = useImagePlaygroundStore();
const modelStore = useModelStore();
const settingsStore = useSettingsStore();
const graphEvents = useGraphEvents();
const { error: showError, success } = useToast();
const { getVideoPlaygroundGallery, deleteFileSystemObject } = useAPI();

const CLOUD_REFERENCE_PICKER_ID = 'video-playground-references';
const VIDEO_GALLERY_PAGE_SIZE = 24;

const { sourceImages, uploadInProgress } = storeToRefs(playgroundStore);
const { activeJobs } = storeToRefs(playgroundStore);
const {
    addSourceFiles,
    cancelJob,
    clearFailedJobs,
    dismissFailedJob,
    hydrateActiveJobs,
    removeSourceImage,
    reorderSourceImages,
    retryFailedJob,
    setSourceImageReorderActive,
    setSourceImagesFromCloud,
    submitVideo,
} = playgroundStore;
const {
    isReady: settingsReady,
    toolsImageGenerationSettings,
} = storeToRefs(settingsStore);
const { isReady: modelsReady } = storeToRefs(modelStore);

const prompt = ref('');
const selectedModel = ref('');
const aspectRatio = ref('16:9');
const resolution = ref('720p');
const duration = ref<number | null>(null);
const generateAudio = ref(false);
const isSubmitting = ref(false);
const isLoadingVideos = ref(false);
const isLoadingMoreVideos = ref(false);
const generatedVideos = ref<GeneratedImageGalleryItem[]>([]);
const generatedVideoTotal = ref(0);
const promptRef = ref<HTMLTextAreaElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const modelQuery = ref('');
const referenceDragSourceIndex = ref<number | null>(null);

const videoAspectRatios = [
    { id: '16:9', w: 16, h: 9 },
    { id: '9:16', w: 9, h: 16 },
    { id: '1:1', w: 1, h: 1 },
    { id: '4:3', w: 4, h: 3 },
    { id: '3:4', w: 3, h: 4 },
    { id: '21:9', w: 21, h: 9 },
    { id: '9:21', w: 9, h: 21 },
];
const videoResolutions = [
    { id: '480p', pixels: 'SD' },
    { id: '720p', pixels: 'HD' },
    { id: '1080p', pixels: 'Full HD' },
    { id: '1K', pixels: '1024 px' },
    { id: '2K', pixels: '2048 px' },
    { id: '4K', pixels: '4096 px' },
];
const durationOptions: Array<{ label: string; value: number | null }> = [
    { label: 'Auto', value: null },
    { label: '4s', value: 4 },
    { label: '6s', value: 6 },
    { label: '8s', value: 8 },
    { label: '10s', value: 10 },
];

const videoModels = computed(() =>
    modelStore.filterCompatibleModels(modelStore.filteredModels, { outputModality: 'video' }),
);
const visibleModels = computed(() => {
    const query = modelQuery.value.trim().toLowerCase();
    if (!query) return videoModels.value.slice(0, 80);
    return videoModels.value
        .filter((model) => model.name.toLowerCase().includes(query))
        .slice(0, 80);
});
const sourceImageIds = computed(() => sourceImages.value.map((image) => image.id));
const isSelectedModelAvailable = computed(() =>
    videoModels.value.some((model) => model.id === selectedModel.value),
);
const videoModelUnavailableMessage = computed(() => {
    if (!modelsReady.value || !settingsReady.value || videoModels.value.length > 0) return '';
    return 'No video models are available with the current model filters. Disable "Hide paid models" to generate video.';
});
const canSubmit = computed(
    () =>
        !isSubmitting.value &&
        prompt.value.trim().length > 0 &&
        isSelectedModelAvailable.value &&
        !videoModelUnavailableMessage.value,
);
const videoJobs = computed(() => activeJobs.value.filter((job) => job.media_type === 'video'));
const isReferenceDragging = computed(() => referenceDragSourceIndex.value !== null);
const hasMoreGeneratedVideos = computed(
    () => generatedVideos.value.length < generatedVideoTotal.value,
);
const failedVideoJobCount = computed(
    () => videoJobs.value.filter((job) => job.status === 'failed').length,
);

const modelDisplayName = (modelId?: string | null) => {
    if (!modelId) return 'Unknown engine';
    return videoModels.value.find((model) => model.id === modelId)?.name || modelId;
};

const setDefaultVideoModel = () => {
    if (!settingsReady.value) return;
    if (selectedModel.value && videoModels.value.some((model) => model.id === selectedModel.value)) {
        return;
    }
    if (!videoModels.value.length) {
        selectedModel.value = '';
        return;
    }
    const configuredModel = toolsImageGenerationSettings.value.defaultVideoModel;
    selectedModel.value = videoModels.value.find((model) => model.id === configuredModel)?.id
        || videoModels.value[0]?.id
        || '';
};

const handleFiles = async (files: FileList | File[] | null) => {
    if (!files) return;
    const list = Array.from(files).filter((file) => file.type.startsWith('image/'));
    if (!list.length) return;
    try {
        await addSourceFiles(list);
        success(`${list.length} reference${list.length > 1 ? 's' : ''} loaded.`, {
            title: 'References ready',
        });
    } catch (error) {
        console.error('Video reference upload failed:', error);
        showError('Could not upload reference images.', { title: 'Upload failed' });
    }
};

const handleFileInputChange = (event: Event) => {
    const input = event.target as HTMLInputElement;
    void handleFiles(input.files);
    input.value = '';
};

const onReferenceDragStart = (event: DragEvent, index: number) => {
    referenceDragSourceIndex.value = index;
    setSourceImageReorderActive(true);
    event.dataTransfer?.setData('text/plain', sourceImages.value[index]?.id || '');
    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
    }
};

const onReferenceDragEnter = (index: number) => {
    if (referenceDragSourceIndex.value === null || referenceDragSourceIndex.value === index) return;
    reorderSourceImages(referenceDragSourceIndex.value, index);
    referenceDragSourceIndex.value = index;
};

const onReferenceDragEnd = () => {
    referenceDragSourceIndex.value = null;
    setSourceImageReorderActive(false);
};

const openCloudReferenceSelect = () => {
    graphEvents.emit('open-attachment-select', {
        nodeId: CLOUD_REFERENCE_PICKER_ID,
        selectedFiles: sourceImages.value,
    });
};

const handleSubmit = async () => {
    if (!canSubmit.value) return;
    isSubmitting.value = true;
    try {
        await submitVideo({
            prompt: prompt.value.trim(),
            model: selectedModel.value,
            aspect_ratio: aspectRatio.value,
            resolution: resolution.value,
            duration: duration.value,
            generate_audio: generateAudio.value,
            source_image_ids: sourceImageIds.value,
        });
        success('Video generation queued.', { title: 'Rendering started' });
    } catch (error) {
        console.error('Video generation failed:', error);
        showError(error instanceof Error ? error.message : 'Could not queue video generation.', {
            title: 'Generation failed',
        });
    } finally {
        isSubmitting.value = false;
    }
};

const handleRetryFailedJob = async (jobId: string) => {
    try {
        await retryFailedJob(jobId);
        success('Failed video generation queued again.', { title: 'Retrying' });
    } catch (error) {
        console.error('Video job retry failed:', error);
        showError('Could not retry failed video generation.', { title: 'Retry failed' });
    }
};

const handleCancelJob = async (jobId: string) => {
    try {
        await cancelJob(jobId);
        success('Video generation cancelled.', { title: 'Cancelled' });
    } catch (error) {
        console.error('Video job cancel failed:', error);
        showError('Could not cancel video generation.', { title: 'Cancel failed' });
    }
};

const handleDismissFailedJob = async (jobId: string) => {
    try {
        await dismissFailedJob(jobId);
    } catch (error) {
        console.error('Video job dismiss failed:', error);
        showError('Could not remove failed video generation.', { title: 'Remove failed' });
    }
};

const handleClearFailedJobs = async () => {
    try {
        await clearFailedJobs();
    } catch (error) {
        console.error('Clear failed video jobs failed:', error);
        showError('Could not clear failed video generations.', { title: 'Clear failed' });
    }
};

const loadGeneratedVideos = async (append = false) => {
    if (append) {
        if (isLoadingMoreVideos.value || isLoadingVideos.value || !hasMoreGeneratedVideos.value) return;
        isLoadingMoreVideos.value = true;
    } else {
        isLoadingVideos.value = true;
    }

    try {
        const response = await getVideoPlaygroundGallery(
            VIDEO_GALLERY_PAGE_SIZE,
            append ? generatedVideos.value.length : 0,
        );
        generatedVideos.value = append
            ? [...generatedVideos.value, ...response.items]
            : response.items;
        generatedVideoTotal.value = response.total;
    } catch (error) {
        console.error('Generated video gallery load failed:', error);
        showError('Could not load generated videos.', { title: 'Gallery failed' });
    } finally {
        if (append) {
            isLoadingMoreVideos.value = false;
        } else {
            isLoadingVideos.value = false;
        }
    }
};

const loadMoreGeneratedVideos = () => loadGeneratedVideos(true);

const deleteVideo = async (video: GeneratedImageGalleryItem) => {
    if (!window.confirm(`Delete "${video.name}"? This cannot be undone.`)) return;

    try {
        await deleteFileSystemObject(video.id);
        generatedVideos.value = generatedVideos.value.filter((item) => item.id !== video.id);
        generatedVideoTotal.value = Math.max(0, generatedVideoTotal.value - 1);
        success('Video archived.', { title: 'Removed' });
    } catch (error) {
        console.error('Video delete failed:', error);
        showError('Could not delete video.', { title: 'Delete failed' });
    }
};

const reuseVideoSettings = (video: GeneratedImageGalleryItem) => {
    prompt.value = video.prompt || video.effective_prompt || '';
    selectedModel.value = video.model || selectedModel.value;
    aspectRatio.value = video.aspect_ratio || '16:9';
    resolution.value = video.resolution || '720p';
    duration.value = video.duration ?? null;
    generateAudio.value = video.generate_audio ?? false;
    sourceImages.value = video.source_image_ids.map((id, index) => ({
        id,
        name: `Reference ${index + 1}`,
        path: `/Referenced Images/${id}`,
        type: 'file',
        content_type: 'image/*',
        created_at: video.created_at,
        updated_at: video.updated_at,
        cached: false,
    }));
    success('Video settings restored.', { title: 'Reset to reel' });
    promptRef.value?.focus();
};

const onPromptKeydown = (event: KeyboardEvent) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        void handleSubmit();
    }
};

watch(
    [videoModels, () => toolsImageGenerationSettings.value.defaultVideoModel, settingsReady],
    setDefaultVideoModel,
    { immediate: true },
);

watch(
    () => activeJobs.value.filter((job) => job.media_type === 'video').map((job) => job.id),
    (currentIds, previousIds) => {
        if (!previousIds || currentIds.length >= previousIds.length) return;
        void loadGeneratedVideos();
    },
);

onMounted(() => {
    void loadGeneratedVideos();
    void hydrateActiveJobs();

    const unsubscribe = graphEvents.on('close-attachment-select', ({ nodeId, selectedFiles }) => {
        if (nodeId !== CLOUD_REFERENCE_PICKER_ID) return;
        const selectedCount = selectedFiles.length;
        setSourceImagesFromCloud(selectedFiles);
        const imageCount = sourceImages.value.length;

        if (imageCount) {
            success(`${imageCount} cloud reference${imageCount > 1 ? 's' : ''} selected.`, {
                title: 'References ready',
            });
        }
        if (selectedCount > imageCount) {
            showError('Only image files can be used as video references.', {
                title: 'Some files skipped',
            });
        }
    });

    onUnmounted(unsubscribe);
});

defineExpose({
    focusPrompt: () => promptRef.value?.focus(),
    handleFiles,
});
</script>

<template>
    <main
        class="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[440px_1fr]
            xl:grid-cols-[470px_1fr] 2xl:grid-cols-[500px_1fr]"
    >
        <aside
            class="border-stone-gray/12 bg-anthracite/45 hidden_scrollbar_y relative min-h-0
                overflow-y-auto rounded-3xl border backdrop-blur-md"
        >
            <div class="space-y-7 p-5 pb-6">
                <section>
                    <div class="flex items-center gap-2.5">
                        <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]">
                            01
                        </span>
                        <span
                            class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                                uppercase"
                        >
                            Motion Directive
                        </span>
                        <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                    </div>
                    <div
                        class="border-stone-gray/15 focus-within:border-ember-glow/55 relative mt-3
                            rounded-2xl border transition-[border-color,box-shadow]
                            focus-within:shadow-[0_0_0_3px_rgba(235,94,40,0.08),0_12px_38px_-16px_rgba(235,94,40,0.45)]"
                    >
                        <textarea
                            ref="promptRef"
                            v-model="prompt"
                            rows="7"
                            class="bg-obsidian/60 text-soft-silk placeholder:text-stone-gray/45 relative
                                w-full resize-none rounded-2xl px-4 py-3.5 text-sm leading-relaxed
                                outline-none custom_scroll"
                            placeholder="Describe the shot, camera movement, subject motion, lighting, and pacing..."
                            @keydown="onPromptKeydown"
                        />
                        <div
                            class="text-stone-gray/50 absolute right-3 bottom-2.5 font-mono text-[9px]
                                tracking-widest uppercase"
                        >
                            ⌘ ⏎ to render
                        </div>
                    </div>
                </section>

                <section>
                    <div class="flex items-center gap-2.5">
                        <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]">
                            04
                        </span>
                        <span
                            class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                                uppercase"
                        >
                            Audio
                        </span>
                        <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                    </div>
                    <button
                        type="button"
                        class="border-stone-gray/14 bg-soft-silk/[0.03] mt-3 flex w-full items-center
                            justify-between gap-4 rounded-2xl border p-3.5 text-left transition
                            hover:border-ember-glow/45 hover:bg-ember-glow/5"
                        :class="generateAudio
                            ? 'border-ember-glow/45 bg-ember-glow/8'
                            : ''"
                        @click="generateAudio = !generateAudio"
                    >
                        <span class="flex min-w-0 items-center gap-3">
                            <span
                                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
                                    border border-stone-gray/15 bg-obsidian/50"
                            >
                                <UiIcon
                                    :name="generateAudio
                                        ? 'MaterialSymbolsVolumeUpRounded'
                                        : 'MaterialSymbolsVolumeOffRounded'"
                                    class="h-5 w-5"
                                    :class="generateAudio ? 'text-ember-glow' : 'text-stone-gray'"
                                />
                            </span>
                            <span class="min-w-0">
                                <span class="font-outfit text-soft-silk block text-sm font-bold">
                                    {{ generateAudio ? 'Generate with audio' : 'Silent video' }}
                                </span>
                                <span class="text-stone-gray/65 mt-0.5 block text-xs leading-5">
                                    Request synchronized audio when the selected model supports it.
                                </span>
                            </span>
                        </span>
                        <span
                            class="relative h-6 w-11 shrink-0 rounded-full border transition"
                            :class="generateAudio
                                ? 'border-ember-glow/45 bg-ember-glow/80'
                                : 'border-stone-gray/20 bg-obsidian'"
                        >
                            <span
                                class="absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-soft-silk
                                    transition"
                                :class="generateAudio ? 'left-6' : 'left-1'"
                            />
                        </span>
                    </button>
                </section>

                <section>
                    <div class="flex items-center gap-2.5">
                        <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]">
                            02
                        </span>
                        <span
                            class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                                uppercase"
                        >
                            Models
                        </span>
                        <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                        <span class="text-ember-glow ml-auto font-mono text-[10px] tabular-nums">
                            × {{ isSelectedModelAvailable ? 1 : 0 }}
                        </span>
                    </div>
                    <div class="relative mt-3">
                        <UiIcon
                            name="MdiMagnify"
                            class="text-stone-gray/50 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
                        />
                        <input
                            v-model="modelQuery"
                            class="border-stone-gray/15 bg-obsidian/60 focus:border-ember-glow/60
                                placeholder:text-stone-gray/45 w-full rounded-xl border px-3 py-1.5 pl-9
                                text-sm outline-none"
                            placeholder="Filter video models…"
                        />
                    </div>
                    <div
                        v-if="!modelsReady"
                        class="mt-2 grid max-h-64 grid-cols-3 gap-1.5 overflow-y-hidden pt-0.5 pr-1"
                    >
                        <div
                            v-for="n in 15"
                            :key="n"
                            class="border-stone-gray/10 bg-anthracite/30 atelier-skeleton min-h-22
                                rounded-xl border"
                        />
                    </div>
                    <div
                        v-else
                        class="custom_scroll hover_scrollbar_y mt-2 grid max-h-64 grid-cols-3 gap-1.5
                            overflow-y-auto pt-0.5 pr-1"
                    >
                        <button
                            v-for="model in visibleModels"
                            :key="model.id"
                            class="relative flex min-h-22 flex-col items-center justify-between gap-2
                                rounded-xl border p-2.5 text-center text-xs transition
                                hover:-translate-y-px"
                            :class="
                                selectedModel === model.id
                                    ? `border-ember-glow bg-ember-glow/12 text-ember-glow
                                        shadow-[inset_0_0_0_1px_rgba(235,94,40,0.2),0_0_28px_-8px_rgba(235,94,40,0.45)]`
                                    : `border-stone-gray/12 bg-soft-silk/4 text-soft-silk/80
                                        hover:border-stone-gray/32`
                            "
                            type="button"
                            @click="selectedModel = model.id"
                        >
                            <span
                                v-if="selectedModel === model.id"
                                class="bg-ember-glow absolute top-2 right-2 h-1.5 w-1.5 rounded-full
                                    shadow-[0_0_10px_rgba(235,94,40,0.9)]"
                            />
                            <span
                                class="border-stone-gray/15 bg-obsidian/70 flex h-9 w-9 items-center
                                    justify-center rounded-lg border transition"
                            >
                                <UiIcon
                                    :name="imagePlaygroundModelIcon(model)"
                                    class="h-5 w-5"
                                    :title="model.provider"
                                />
                            </span>
                            <span class="line-clamp-2 w-full text-[11px] leading-tight font-semibold">
                                {{ model.name }}
                            </span>
                        </button>
                        <p
                            v-if="!visibleModels.length"
                            class="text-stone-gray col-span-3 p-6 text-center text-sm"
                        >
                            {{ videoModelUnavailableMessage || 'No video models match.' }}
                        </p>
                    </div>
                </section>

                <section>
                    <div class="flex items-center gap-2.5">
                        <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]">
                            03
                        </span>
                        <span
                            class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                                uppercase"
                        >
                            Frame
                        </span>
                        <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                    </div>
                    <p class="text-stone-gray/60 mt-2 text-[10px] tracking-[0.25em] uppercase">
                        Aspect
                    </p>
                    <div class="mt-2 grid grid-cols-4 gap-1.5">
                        <button
                            v-for="ratio in videoAspectRatios"
                            :key="ratio.id"
                            type="button"
                            class="group/ratio flex flex-col items-center justify-center gap-1.5
                                rounded-xl border p-2 text-[10px] font-semibold tracking-wider uppercase
                                transition"
                            :class="
                                aspectRatio === ratio.id
                                    ? 'border-ember-glow bg-ember-glow/10 text-ember-glow'
                                    : `border-stone-gray/15 bg-obsidian/40 text-stone-gray
                                        hover:text-soft-silk hover:border-stone-gray/40`
                            "
                            @click="aspectRatio = ratio.id"
                        >
                            <span
                                class="inline-block rounded-[2px] bg-current opacity-55
                                    transition-opacity group-hover/ratio:opacity-85"
                                :style="{
                                    width: `${(ratio.w / Math.max(ratio.w, ratio.h)) * 22}px`,
                                    height: `${(ratio.h / Math.max(ratio.w, ratio.h)) * 22}px`,
                                }"
                            />
                            {{ ratio.id }}
                        </button>
                    </div>
                    <p class="text-stone-gray/60 mt-3 text-[10px] tracking-[0.25em] uppercase">
                        Resolution
                    </p>
                    <div class="mt-2 grid grid-cols-3 gap-1.5">
                        <button
                            v-for="res in videoResolutions"
                            :key="res.id"
                            type="button"
                            class="rounded-xl border px-2 py-2.5 text-center transition"
                            :class="
                                resolution === res.id
                                    ? 'border-ember-glow bg-ember-glow/10 text-ember-glow'
                                    : `border-stone-gray/15 bg-obsidian/40 text-stone-gray
                                        hover:text-soft-silk hover:border-stone-gray/40`
                            "
                            @click="resolution = res.id"
                        >
                            <div class="font-outfit text-base leading-none font-bold">{{ res.id }}</div>
                            <div class="mt-0.5 font-mono text-[9px] opacity-60">{{ res.pixels }}</div>
                        </button>
                    </div>
                    <p class="text-stone-gray/60 mt-3 text-[10px] tracking-[0.25em] uppercase">
                        Duration
                    </p>
                    <div class="mt-2 grid grid-cols-5 gap-1.5">
                        <button
                            v-for="item in durationOptions"
                            :key="item.label"
                            type="button"
                            class="rounded-xl border px-2 py-2.5 text-center transition"
                            :class="
                                duration === item.value
                                    ? 'border-ember-glow bg-ember-glow/10 text-ember-glow'
                                    : `border-stone-gray/15 bg-obsidian/40 text-stone-gray
                                        hover:text-soft-silk hover:border-stone-gray/40`
                            "
                            @click="duration = item.value"
                        >
                            <div class="font-outfit text-sm leading-none font-bold">{{ item.label }}</div>
                        </button>
                    </div>
                    <div
                        v-if="sourceImages.length"
                        class="border-ember-glow/25 bg-ember-glow/8 text-ember-glow mt-3 flex gap-2
                            rounded-xl border px-3 py-2 text-xs leading-snug"
                    >
                        <UiIcon name="UilExclamationTriangle" class="h-4 w-4 shrink-0" />
                        <span>Reference guidance can make models ignore requested frame settings.</span>
                    </div>
                </section>

                <section>
                    <div class="flex items-center gap-2.5">
                        <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]">
                            05
                        </span>
                        <span
                            class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                                uppercase"
                        >
                            References
                        </span>
                        <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                        <span class="text-stone-gray/50 ml-auto text-[9px] tracking-wider uppercase">
                            Optional
                        </span>
                    </div>
                    <div class="mt-3 grid grid-cols-2 gap-1.5">
                        <button
                            type="button"
                            class="group/drop border-stone-gray/18 bg-anthracite/40
                                hover:border-ember-glow/55 hover:bg-ember-glow/4 flex min-h-28 flex-col
                                items-center justify-center gap-1.5 rounded-2xl border border-dashed
                                py-5 transition"
                            @click="fileInput?.click()"
                        >
                            <UiIcon
                                name="UilUpload"
                                class="text-stone-gray/70 group-hover/drop:text-ember-glow h-7 w-7
                                    transition"
                            />
                            <span class="text-soft-silk/85 text-center text-sm font-semibold">
                                {{ uploadInProgress ? 'Uploading…' : 'Drop or click' }}
                            </span>
                            <span
                                class="text-stone-gray/50 font-mono text-[9px] tracking-widest
                                    uppercase"
                            >
                                Device
                            </span>
                        </button>
                        <button
                            type="button"
                            class="group/drop border-stone-gray/18 bg-anthracite/40
                                hover:border-ember-glow/55 hover:bg-ember-glow/4 flex min-h-28 flex-col
                                items-center justify-center gap-1.5 rounded-2xl border border-dashed
                                py-5 transition"
                            @click="openCloudReferenceSelect"
                        >
                            <UiIcon
                                name="MdiCloudUploadOutline"
                                class="text-stone-gray/70 group-hover/drop:text-ember-glow h-7 w-7
                                    transition"
                            />
                            <span class="text-soft-silk/85 text-center text-sm font-semibold">
                                Meridian cloud
                            </span>
                            <span
                                class="text-stone-gray/50 font-mono text-[9px] tracking-widest
                                    uppercase"
                            >
                                Browse files
                            </span>
                        </button>
                    </div>
                    <input
                        ref="fileInput"
                        type="file"
                        accept="image/*"
                        multiple
                        class="hidden"
                        :disabled="uploadInProgress"
                        @change="handleFileInputChange"
                    />
                    <TransitionGroup
                        v-if="sourceImages.length"
                        name="reference-list"
                        tag="div"
                        class="mt-3 grid grid-cols-4 gap-1.5"
                        :class="{ 'no-transition': isReferenceDragging }"
                    >
                        <div
                            v-for="(image, index) in sourceImages"
                            :key="image.id"
                            class="border-stone-gray/15 group/ref bg-obsidian/60 relative aspect-square
                                overflow-hidden rounded-lg border"
                            :class="{
                                'cursor-grab active:cursor-grabbing': true,
                                'scale-95 border-dashed opacity-45': referenceDragSourceIndex === index,
                            }"
                            draggable="true"
                            @dragstart.stop="onReferenceDragStart($event, index)"
                            @dragenter.prevent.stop="onReferenceDragEnter(index)"
                            @dragover.prevent.stop
                            @drop.prevent.stop="onReferenceDragEnd"
                            @dragend.stop="onReferenceDragEnd"
                        >
                            <img
                                :src="imagePlaygroundImageUrl(image.id, true)"
                                :alt="image.name"
                                class="h-full w-full object-cover"
                            />
                            <button
                                type="button"
                                class="absolute top-1 right-1 flex h-5 w-5 items-center justify-center
                                    rounded-full bg-black/75 text-white opacity-0 transition
                                    group-hover/ref:opacity-100 hover:bg-red-500/80"
                                aria-label="Remove reference image"
                                @click.stop="removeSourceImage(image.id)"
                            >
                                <UiIcon name="MaterialSymbolsClose" class="h-3 w-3" />
                            </button>
                        </div>
                    </TransitionGroup>
                </section>
            </div>

            <div
                class="border-stone-gray/10 from-anthracite/85 to-anthracite/95 sticky bottom-0 border-t
                    bg-linear-to-t p-4 backdrop-blur-md"
            >
                <p
                    v-if="videoModelUnavailableMessage"
                    class="text-amber-200/85 mb-3 rounded-xl border border-amber-300/20 bg-amber-300/10
                        px-3 py-2 text-xs leading-5"
                >
                    {{ videoModelUnavailableMessage }}
                </p>
                <button
                    type="button"
                    class="text-obsidian group relative isolate w-full overflow-hidden rounded-2xl px-4
                        py-3.5 disabled:cursor-not-allowed disabled:opacity-40"
                    :disabled="!canSubmit"
                    @click="handleSubmit"
                >
                    <span
                        class="via-ember-glow absolute inset-0 z-0 bg-linear-to-r from-[#f76e3a]
                            to-[#c44a1c] transition duration-300 group-hover:scale-[1.02]
                            group-hover:brightness-110 hover:scale-[1.02]"
                    />
                    <span
                        class="pointer-events-none absolute inset-0 z-0 bg-radial-[120px_60px_at_30%_0%]
                            from-white/35 to-transparent opacity-70"
                    />
                    <span class="relative z-10 flex items-center justify-center gap-3">
                        <UiIcon
                            :name="isSubmitting ? 'LineMdLoadingTwotoneLoop' : 'MaterialSymbolsVideoCameraBackRounded'"
                            class="h-4 w-4"
                        />
                        <span class="font-outfit text-[15px] font-bold tracking-tight">
                            {{ isSubmitting ? 'Rendering…' : 'Create' }}
                        </span>
                    </span>
                </button>
            </div>
        </aside>

        <section
            class="border-stone-gray/12 bg-anthracite/30 relative min-h-0 overflow-hidden rounded-3xl
                border backdrop-blur-md"
        >
            <div
                class="border-stone-gray/12 flex flex-wrap items-center justify-between gap-3 border-b
                    px-5 py-3"
            >
                <div class="flex items-baseline gap-3">
                    <h2 class="font-outfit text-soft-silk text-2xl font-bold tracking-tight">
                        Video Reels
                    </h2>
                    <span class="text-stone-gray/55 font-mono text-[10px] tracking-widest uppercase">
                        {{ generatedVideoTotal }} saved
                    </span>
                </div>
                <span class="text-stone-gray/65 text-xs">
                    Videos are saved to your files when generation completes.
                </span>
            </div>

            <div class="hidden_scrollbar_y h-full overflow-y-auto p-5 pb-24">
                <UiImagesPlaygroundActiveJobsLane
                    :jobs="videoJobs"
                    :failed-job-count="failedVideoJobCount"
                    :model-display-name="modelDisplayName"
                    @retry="handleRetryFailedJob"
                    @dismiss="handleDismissFailedJob"
                    @cancel="handleCancelJob"
                    @clear-failed="handleClearFailedJobs"
                />

                <div
                    v-if="(isSubmitting || isLoadingVideos) && !generatedVideos.length"
                    class="border-stone-gray/12 bg-obsidian/45 flex min-h-[24rem] items-center justify-center
                        rounded-3xl border text-center"
                >
                    <div>
                        <UiIcon name="MingcuteLoading3Fill" class="text-ember-glow mx-auto h-10 w-10" />
                        <p class="text-soft-silk mt-4 text-sm font-semibold">
                            {{ isLoadingVideos ? 'Loading generated videos' : 'Rendering with OpenRouter' }}
                        </p>
                        <p class="text-stone-gray mt-1 text-xs">
                            {{ isLoadingVideos ? 'Loading saved videos.' : 'This can take several minutes.' }}
                        </p>
                    </div>
                </div>

                <div
                    v-else-if="!generatedVideos.length"
                    class="border-stone-gray/12 bg-obsidian/45 flex min-h-[24rem] items-center justify-center
                        rounded-3xl border text-center"
                >
                    <div class="max-w-md px-6">
                        <UiIcon
                            name="MaterialSymbolsVideoCameraBackRounded"
                            class="text-ember-glow mx-auto h-10 w-10"
                        />
                        <h3 class="font-outfit text-soft-silk mt-4 text-2xl font-bold">
                            Generate motion from a prompt.
                        </h3>
                        <p class="text-stone-gray mt-2 text-sm leading-6">
                            Pick a video-capable model, describe the shot, and optionally attach image
                            references for character, style, or first-frame guidance.
                        </p>
                    </div>
                </div>

                <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <article
                        v-for="video in generatedVideos"
                        :key="video.id"
                        class="border-stone-gray/12 bg-obsidian/55 overflow-hidden rounded-3xl border"
                    >
                        <video
                            :src="imagePlaygroundImageUrl(video.id)"
                            class="bg-obsidian aspect-video w-full object-contain"
                            controls
                            preload="metadata"
                            playsinline
                        />
                        <div class="space-y-3 p-4">
                            <div>
                                <p class="text-soft-silk line-clamp-2 text-sm font-semibold">
                                    {{ video.prompt || video.name }}
                                </p>
                                <p class="text-stone-gray/70 mt-1 text-[11px]">
                                    {{ video.model || 'Saved video' }} · {{ video.aspect_ratio || 'source' }} ·
                                    {{ video.resolution || 'file' }} ·
                                    {{ video.generate_audio ? 'audio' : 'silent' }} ·
                                    {{ imagePlaygroundFormatBytes(video.size) }}
                                </p>
                            </div>
                            <div class="flex gap-2">
                                <button
                                    type="button"
                                    class="border-stone-gray/15 text-soft-silk hover:border-ember-glow/45
                                        hover:text-ember-glow flex flex-1 items-center justify-center gap-2
                                        rounded-xl border bg-soft-silk/5 px-3 py-2 text-xs font-semibold
                                        transition"
                                    title="Reuse settings"
                                    @click="reuseVideoSettings(video)"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsControlPointDuplicateOutlineRounded"
                                        class="h-4 w-4"
                                    />
                                    Reuse settings
                                </button>
                                <a
                                    :href="imagePlaygroundDownloadUrl(video.id)"
                                    :download="imagePlaygroundDownloadName(video)"
                                    class="border-stone-gray/15 text-soft-silk hover:border-ember-glow/45
                                        hover:text-ember-glow flex items-center justify-center gap-2
                                        rounded-xl border bg-soft-silk/5 px-3 py-2 text-xs font-semibold
                                        transition"
                                >
                                    <UiIcon name="UilDownloadAlt" class="h-4 w-4" />
                                </a>
                                <button
                                    type="button"
                                    class="border-red-300/20 bg-red-500/10 px-3 py-2 text-red-100 transition
                                        hover:bg-red-500/20 rounded-xl border"
                                    title="Delete video"
                                    @click="deleteVideo(video)"
                                >
                                    <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    </article>
                </div>

                <div class="flex justify-center py-6">
                    <button
                        v-if="hasMoreGeneratedVideos"
                        type="button"
                        class="border-stone-gray/15 hover:border-ember-glow/50 text-stone-gray
                            hover:text-soft-silk rounded-full border px-5 py-2 text-xs tracking-widest
                            uppercase transition disabled:cursor-not-allowed disabled:opacity-40"
                        :disabled="isLoadingMoreVideos"
                        @click="loadMoreGeneratedVideos"
                    >
                        {{ isLoadingMoreVideos ? 'Loading…' : 'Load more' }}
                    </button>
                    <span
                        v-else-if="generatedVideos.length"
                        class="text-stone-gray/40 font-mono text-[10px] tracking-widest uppercase"
                    >
                        — End of reels —
                    </span>
                </div>
            </div>
        </section>
    </main>
</template>

<style scoped>
.reference-list-move,
.reference-list-enter-active,
.reference-list-leave-active {
    transition: all 0.2s ease;
}

.reference-list-enter-from,
.reference-list-leave-to {
    opacity: 0;
    transform: scale(0.95);
}

.reference-list-leave-active {
    position: absolute;
}

.no-transition .reference-list-move,
.no-transition .reference-list-enter-active,
.no-transition .reference-list-leave-active {
    transition: none !important;
}
</style>
