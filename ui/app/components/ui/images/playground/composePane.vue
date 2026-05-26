<script lang="ts" setup>
import {
    IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH,
    IMAGE_STYLE_PRESETS,
} from '@/stores/imagePlayground';
import {
    IMAGE_PLAYGROUND_ASPECT_RATIOS,
    IMAGE_PLAYGROUND_RESOLUTIONS,
    IMAGE_PLAYGROUND_STYLE_VISUALS,
    imagePlaygroundImageUrl,
    imagePlaygroundModelIcon,
} from '@/utils/imagePlayground';

const playgroundStore = useImagePlaygroundStore();
const modelStore = useModelStore();
const { error: showError, success } = useToast();
const graphEvents = useGraphEvents();
const { isReady: modelsReady } = storeToRefs(modelStore);

const CLOUD_REFERENCE_PICKER_ID = 'image-playground-references';

const {
    aspectRatio,
    exceedsBatchLimit,
    generationCount,
    isSubmitting,
    lastError,
    prompt,
    promptHistory,
    resolution,
    selectedModels,
    sourceImages,
    stylePreset,
    uploadInProgress,
    variationCount,
} = storeToRefs(playgroundStore);
const {
    addSourceFiles,
    applyPromptHistory,
    clearPromptHistory,
    loadPromptHistory,
    removeSourceImage,
    removePromptHistory,
    reorderSourceImages,
    selectOnlyModel,
    setDefaultModel,
    setSourceImagesFromCloud,
    submit,
    toggleModel,
} = playgroundStore;

const fileInput = ref<HTMLInputElement | null>(null);
const modelQuery = ref('');
const promptRef = ref<HTMLTextAreaElement | null>(null);
const isPromptHistoryOpen = ref(false);
const isDraggingIteration = ref(false);
const referenceDragSourceIndex = ref<number | null>(null);

const imageModels = computed(() =>
    modelStore.filterCompatibleModels(modelStore.filteredModels, { outputModality: 'image' }),
);

const visibleModels = computed(() => {
    const query = modelQuery.value.trim().toLowerCase();
    if (!query) return imageModels.value.slice(0, 80);
    return imageModels.value
        .filter((model) => model.name.toLowerCase().includes(query))
        .slice(0, 80);
});

const trimmedPromptLength = computed(() => prompt.value.trim().length);
const canSubmit = computed(
    () =>
        !isSubmitting.value &&
        trimmedPromptLength.value > 0 &&
        selectedModels.value.length > 0 &&
        !exceedsBatchLimit.value,
);
const iterationProgress = computed(() => `${((variationCount.value - 1) / 15) * 100}%`);
const isReferenceDragging = computed(() => referenceDragSourceIndex.value !== null);

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
        console.error('Reference upload failed:', error);
        showError('Could not upload reference images.', { title: 'Upload failed' });
    }
};

const handleSubmit = async () => {
    if (exceedsBatchLimit.value) {
        showError(
            `Maximum ${IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH} images per batch. Reduce models or iterations.`,
            { title: 'Batch too large' },
        );
        return;
    }
    if (!canSubmit.value) return;
    try {
        await submit();
        success('Batch queued for development.', { title: 'In the darkroom' });
    } catch (error) {
        console.error('Image generation submit failed:', error);
        showError(lastError.value || 'Could not queue image generation.', {
            title: 'Generation failed',
        });
    }
};

const onPromptKeydown = (event: KeyboardEvent) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        void handleSubmit();
    }
};

const onFileInputChange = (event: Event) => {
    const input = event.target as HTMLInputElement;
    void handleFiles(input.files);
    input.value = '';
};

const updateIterationFromPointer = (event: PointerEvent) => {
    const input = event.currentTarget as HTMLInputElement;
    const rect = input.getBoundingClientRect();
    const progress = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    variationCount.value = Math.round(progress * 15) + 1;
};

const onIterationPointerDown = (event: PointerEvent) => {
    const input = event.currentTarget as HTMLInputElement;
    isDraggingIteration.value = true;
    input.setPointerCapture(event.pointerId);
    updateIterationFromPointer(event);
};

const onIterationPointerMove = (event: PointerEvent) => {
    if (!isDraggingIteration.value) return;
    updateIterationFromPointer(event);
};

const onIterationPointerEnd = (event: PointerEvent) => {
    const input = event.currentTarget as HTMLInputElement;
    isDraggingIteration.value = false;
    if (input.hasPointerCapture(event.pointerId)) {
        input.releasePointerCapture(event.pointerId);
    }
};

const onReferenceDragStart = (event: DragEvent, index: number) => {
    referenceDragSourceIndex.value = index;
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
};

const openCloudReferenceSelect = () => {
    graphEvents.emit('open-attachment-select', {
        nodeId: CLOUD_REFERENCE_PICKER_ID,
        selectedFiles: sourceImages.value,
    });
};

watch(
    imageModels,
    (models) => {
        setDefaultModel(models[0]?.id || '');
    },
    { immediate: true },
);

onMounted(() => {
    loadPromptHistory();
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
            showError('Only image files can be used as references.', {
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
    <aside
        class="border-stone-gray/12 bg-anthracite/45 hidden_scrollbar_y relative min-h-0
            overflow-y-auto rounded-3xl border backdrop-blur-md"
    >
        <div class="space-y-7 p-5 pb-6">
            <section>
                <div class="flex items-center gap-2.5">
                    <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]"
                        >01</span
                    >
                    <span
                        class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                            uppercase"
                    >
                        Directive
                    </span>
                    <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                    <span class="text-stone-gray/60 ml-auto font-mono text-[10px] tabular-nums">
                        {{ trimmedPromptLength }}
                    </span>
                    <button
                        type="button"
                        class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray
                            hover:border-ember-glow/45 hover:text-ember-glow flex items-center gap-1
                            rounded-full border px-2 py-1 font-mono text-[9px] tracking-wider
                            uppercase transition"
                        @click="isPromptHistoryOpen = !isPromptHistoryOpen"
                    >
                        <UiIcon name="MaterialSymbolsHistory" class="h-3 w-3" />
                        <div class="h-2.5">{{ promptHistory.length }}</div>
                    </button>
                </div>
                <div
                    class="border-stone-gray/15 focus-within:border-ember-glow/55 relative mt-3
                        rounded-2xl border transition-[border-color,box-shadow]
                        focus-within:shadow-[0_0_0_3px_rgba(235,94,40,0.08),0_12px_38px_-16px_rgba(235,94,40,0.45)]"
                >
                    <textarea
                        ref="promptRef"
                        v-model="prompt"
                        rows="6"
                        class="bg-obsidian/60 text-soft-silk placeholder:text-stone-gray/45 relative
                            w-full resize-none rounded-2xl px-4 py-3.5 text-sm leading-relaxed
                            outline-none custom_scroll"
                        placeholder="Describe the frame you want to develop…"
                        @keydown="onPromptKeydown"
                    />
                    <div
                        class="text-stone-gray/50 absolute right-3 bottom-2.5 font-mono text-[9px]
                            tracking-widest uppercase"
                    >
                        ⌘ ⏎ to develop
                    </div>
                </div>
                <div
                    v-if="isPromptHistoryOpen"
                    class="border-stone-gray/12 bg-obsidian/35 mt-2 overflow-hidden rounded-2xl
                        border"
                >
                    <div
                        class="border-stone-gray/10 flex items-center justify-between border-b px-3
                            py-2"
                    >
                        <span
                            class="text-soft-silk font-mono text-[10px] tracking-[0.24em] uppercase"
                        >
                            Prompt history
                        </span>
                        <button
                            v-if="promptHistory.length"
                            type="button"
                            class="text-stone-gray font-mono text-[9px] tracking-wider uppercase
                                transition hover:text-red-300"
                            @click="clearPromptHistory"
                        >
                            Clear
                        </button>
                    </div>
                    <div v-if="promptHistory.length" class="max-h-56 overflow-y-auto p-1.5 custom_scroll">
                        <div
                            v-for="entry in promptHistory"
                            :key="entry"
                            class="group/history hover:bg-soft-silk/5 flex items-start gap-2
                                rounded-xl p-2 transition"
                        >
                            <button
                                type="button"
                                class="min-w-0 flex-1 text-left"
                                @click="applyPromptHistory(entry)"
                            >
                                <span class="text-soft-silk line-clamp-2 text-xs leading-snug">
                                    {{ entry }}
                                </span>
                            </button>
                            <button
                                type="button"
                                class="text-stone-gray/45 flex h-6 w-6 shrink-0 items-center
                                    justify-center rounded-full opacity-0 transition
                                    group-hover/history:opacity-100 hover:text-red-300"
                                aria-label="Remove prompt history item"
                                @click="removePromptHistory(entry)"
                            >
                                <UiIcon name="MaterialSymbolsClose" class="h-3.5 w-3.5" />
                            </button>
                        </div>
                    </div>
                    <p v-else class="text-stone-gray/60 px-3 py-4 text-center text-xs">
                        Submitted prompts appear here.
                    </p>
                </div>
            </section>

            <section>
                <div class="flex items-center gap-2.5">
                    <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]"
                        >02</span
                    >
                    <span
                        class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                            uppercase"
                    >
                        Models
                    </span>
                    <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                    <span class="text-ember-glow ml-auto font-mono text-[10px] tabular-nums">
                        × {{ selectedModels.length }}
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
                        placeholder="Filter image models…"
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
                            selectedModels.includes(model.id)
                                ? `border-ember-glow bg-ember-glow/12 text-ember-glow
                                    shadow-[inset_0_0_0_1px_rgba(235,94,40,0.2),0_0_28px_-8px_rgba(235,94,40,0.45)]`
                                : `border-stone-gray/12 bg-soft-silk/4 text-soft-silk/80
                                    hover:border-stone-gray/32`
                        "
                        type="button"
                        @click="toggleModel(model.id)"
                        @dblclick="selectOnlyModel(model.id)"
                    >
                        <span
                            v-if="selectedModels.includes(model.id)"
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
                        No image models match.
                    </p>
                </div>
            </section>

            <section>
                <div class="flex items-center gap-2.5">
                    <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]"
                        >03</span
                    >
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
                <div class="mt-2 grid grid-cols-5 gap-1.5">
                    <button
                        v-for="ratio in IMAGE_PLAYGROUND_ASPECT_RATIOS"
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
                        v-for="res in IMAGE_PLAYGROUND_RESOLUTIONS"
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
                <div
                    v-if="sourceImages.length"
                    class="border-ember-glow/25 bg-ember-glow/8 text-ember-glow mt-3 flex gap-2
                        rounded-xl border px-3 py-2 text-xs leading-snug"
                >
                    <UiIcon name="UilExclamationTriangle" class="h-4 w-4 shrink-0" />
                    <span>
                        Reference editing can make models ignore requested aspect ratio or
                        resolution.
                    </span>
                </div>
            </section>

            <section>
                <div class="flex items-center gap-2.5">
                    <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]"
                        >04</span
                    >
                    <span
                        class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                            uppercase"
                    >
                        Tone
                    </span>
                    <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                </div>
                <div class="mt-3 grid grid-cols-3 gap-1.5">
                    <button
                        v-for="(preset, key) in IMAGE_STYLE_PRESETS"
                        :key="key"
                        type="button"
                        class="bg-anthracite/55 group/tone overflow-hidden rounded-xl border
                            text-left transition hover:-translate-y-px"
                        :class="
                            stylePreset === key
                                ? 'border-ember-glow shadow-[0_0_24px_rgba(235,94,40,0.2)]'
                                : 'border-stone-gray/12 hover:border-stone-gray/35'
                        "
                        @click="stylePreset = key"
                    >
                        <span class="bg-obsidian/60 relative block h-14 w-full overflow-hidden">
                            <img
                                v-if="IMAGE_PLAYGROUND_STYLE_VISUALS[key]?.image"
                                :src="IMAGE_PLAYGROUND_STYLE_VISUALS[key]?.image"
                                :alt="`${preset.label} illustration`"
                                style="image-rendering: auto"
                                class="h-full w-full object-cover transition duration-500"
                            />
                            <span
                                v-else
                                class="from-stone-gray/25 to-stone-gray/8 block h-full w-full
                                    bg-linear-to-br"
                            />
                            <span
                                class="absolute inset-0 bg-linear-to-t from-black/35 via-transparent
                                    to-white/5"
                            />
                        </span>
                        <span class="block px-2 py-1.5">
                            <span
                                class="font-outfit block truncate text-[11px] font-bold"
                                :class="
                                    stylePreset === key ? 'text-ember-glow' : 'text-soft-silk/90'
                                "
                            >
                                {{ preset.label }}
                            </span>
                            <span
                                class="text-stone-gray/60 block truncate text-[9px] tracking-wider
                                    uppercase"
                            >
                                {{ IMAGE_PLAYGROUND_STYLE_VISUALS[key]?.description }}
                            </span>
                        </span>
                    </button>
                </div>
            </section>

            <section>
                <div class="flex items-center gap-2.5">
                    <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]"
                        >05</span
                    >
                    <span
                        class="text-soft-silk font-mono text-[10px] font-semibold tracking-[0.32em]
                            uppercase"
                    >
                        Iterations
                    </span>
                    <span class="from-soft-silk/18 h-px flex-1 bg-linear-to-r to-transparent" />
                    <span class="text-soft-silk ml-auto font-mono text-[10px] tabular-nums">
                        × {{ variationCount }}
                    </span>
                </div>
                <div
                    class="border-stone-gray/15 bg-obsidian/40 mt-3 rounded-2xl border px-4 py-1.5"
                >
                    <input
                        v-model.number="variationCount"
                        type="range"
                        min="1"
                        max="16"
                        step="1"
                        class="iteration-slider w-full"
                        :style="{ '--iteration-progress': iterationProgress }"
                        @pointerdown="onIterationPointerDown"
                        @pointermove="onIterationPointerMove"
                        @pointerup="onIterationPointerEnd"
                        @pointercancel="onIterationPointerEnd"
                    />
                    <div class="text-stone-gray/55 mt-1 flex justify-between font-mono text-[9px]">
                        <span>1</span>
                        <span>16</span>
                    </div>
                </div>
                <p class="text-stone-gray/70 mt-2.5 text-[11px]">
                    <span class="text-soft-silk font-semibold">{{ variationCount }}</span>
                    per engine ·
                    <span
                        class="font-semibold"
                        :class="exceedsBatchLimit ? 'text-red-300' : 'text-ember-glow'"
                    >
                        {{ generationCount }}
                    </span>
                    total plate{{ generationCount === 1 ? '' : 's' }}
                </p>
                <p v-if="exceedsBatchLimit" class="mt-2 text-[11px] leading-snug text-red-300/85">
                    Maximum {{ IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH }} plates per batch. Reduce
                    engines or iterations.
                </p>
            </section>

            <section>
                <div class="flex items-center gap-2.5">
                    <span class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.2em]"
                        >06</span
                    >
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
                    @change="onFileInputChange"
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
                        @dragstart="onReferenceDragStart($event, index)"
                        @dragenter.prevent="onReferenceDragEnter(index)"
                        @dragover.prevent
                        @dragend="onReferenceDragEnd"
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
                        :name="isSubmitting ? 'LineMdLoadingTwotoneLoop' : 'MynauiSparklesSolid'"
                        class="h-4 w-4"
                    />
                    <span class="font-outfit text-[15px] font-bold tracking-tight">
                        {{ isSubmitting ? 'Loading…' : 'Create' }}
                    </span>
                    <span
                        class="bg-obsidian/25 ml-1 rounded-full px-2 py-0.5 font-mono text-[10px]
                            tabular-nums"
                    >
                        × {{ generationCount }}
                    </span>
                </span>
            </button>
        </div>
    </aside>
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
