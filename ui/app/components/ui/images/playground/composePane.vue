<script lang="ts" setup>
import { IMAGE_STYLE_PRESETS } from '@/stores/imagePlayground';
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
    isSubmitting,
    lastError,
    prompt,
    resolution,
    selectedModels,
    sourceImages,
    stylePreset,
    uploadInProgress,
    variationCount,
} = storeToRefs(playgroundStore);
const {
    addSourceFiles,
    removeSourceImage,
    selectOnlyModel,
    setDefaultModel,
    setSourceImagesFromCloud,
    submit,
    toggleModel,
} = playgroundStore;

const fileInput = ref<HTMLInputElement | null>(null);
const modelQuery = ref('');
const promptRef = ref<HTMLTextAreaElement | null>(null);
const isDraggingIteration = ref(false);

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

const generationCount = computed(
    () => Math.max(1, variationCount.value) * selectedModels.value.length,
);
const trimmedPromptLength = computed(() => prompt.value.trim().length);
const canSubmit = computed(
    () => !isSubmitting.value && trimmedPromptLength.value > 0 && selectedModels.value.length > 0,
);
const iterationProgress = computed(() => `${((variationCount.value - 1) / 15) * 100}%`);

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
        class="border-stone-gray/12 bg-anthracite/45 custom_scroll hover_scrollbar_y relative
            min-h-0 overflow-y-auto rounded-3xl border backdrop-blur-md"
    >
        <div class="space-y-7 p-5 pb-6">
            <section>
                <div class="atelier-section-head">
                    <span class="atelier-section-num">01</span>
                    <span class="atelier-section-label">Directive</span>
                    <span class="atelier-section-rule" />
                    <span class="text-stone-gray/60 ml-auto font-mono text-[10px] tabular-nums">
                        {{ trimmedPromptLength }}
                    </span>
                </div>
                <div class="prompt-shell mt-3">
                    <textarea
                        ref="promptRef"
                        v-model="prompt"
                        rows="6"
                        class="bg-obsidian/60 text-soft-silk placeholder:text-stone-gray/45 relative
                            w-full resize-none rounded-2xl px-4 py-3.5 text-sm leading-relaxed
                            outline-none"
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
            </section>

            <section>
                <div class="atelier-section-head">
                    <span class="atelier-section-num">02</span>
                    <span class="atelier-section-label">Models</span>
                    <span class="atelier-section-rule" />
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
                        class="engine-chip relative flex min-h-22 flex-col items-center
                            justify-between gap-2 rounded-xl border p-2.5 text-center text-xs"
                        :class="
                            selectedModels.includes(model.id)
                                ? 'engine-chip-active'
                                : 'engine-chip-idle'
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
                <div class="atelier-section-head">
                    <span class="atelier-section-num">03</span>
                    <span class="atelier-section-label">Frame</span>
                    <span class="atelier-section-rule" />
                </div>
                <p class="text-stone-gray/60 mt-2 text-[10px] tracking-[0.25em] uppercase">
                    Aspect
                </p>
                <div class="mt-2 grid grid-cols-5 gap-1.5">
                    <button
                        v-for="ratio in IMAGE_PLAYGROUND_ASPECT_RATIOS"
                        :key="ratio.id"
                        type="button"
                        class="aspect-chip group/ratio flex flex-col items-center justify-center
                            gap-1.5 rounded-xl border p-2 text-[10px] font-semibold tracking-wider
                            uppercase transition"
                        :class="
                            aspectRatio === ratio.id
                                ? 'border-ember-glow bg-ember-glow/10 text-ember-glow'
                                : `border-stone-gray/15 bg-obsidian/40 text-stone-gray
                                    hover:text-soft-silk hover:border-stone-gray/40`
                        "
                        @click="aspectRatio = ratio.id"
                    >
                        <span
                            class="aspect-rect inline-block"
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
                <div class="atelier-section-head">
                    <span class="atelier-section-num">04</span>
                    <span class="atelier-section-label">Tone</span>
                    <span class="atelier-section-rule" />
                </div>
                <div class="mt-3 grid grid-cols-3 gap-1.5">
                    <button
                        v-for="(preset, key) in IMAGE_STYLE_PRESETS"
                        :key="key"
                        type="button"
                        class="tone-chip group/tone overflow-hidden rounded-xl border text-left
                            transition"
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
                <div class="atelier-section-head">
                    <span class="atelier-section-num">05</span>
                    <span class="atelier-section-label">Iterations</span>
                    <span class="atelier-section-rule" />
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
                    <span class="text-ember-glow font-semibold">{{ generationCount }}</span>
                    total plate{{ generationCount === 1 ? '' : 's' }}
                </p>
            </section>

            <section>
                <div class="atelier-section-head">
                    <span class="atelier-section-num">06</span>
                    <span class="atelier-section-label">References</span>
                    <span class="atelier-section-rule" />
                    <span class="text-stone-gray/50 ml-auto text-[9px] tracking-wider uppercase">
                        Optional
                    </span>
                </div>
                <div class="mt-3 grid grid-cols-2 gap-1.5">
                    <button
                        type="button"
                        class="reference-drop group/drop flex min-h-28 flex-col items-center
                            justify-center gap-1.5 rounded-2xl border border-dashed py-5 transition"
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
                        class="reference-drop group/drop flex min-h-28 flex-col items-center
                            justify-center gap-1.5 rounded-2xl border border-dashed py-5 transition"
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
                <div v-if="sourceImages.length" class="mt-3 grid grid-cols-4 gap-1.5">
                    <div
                        v-for="image in sourceImages"
                        :key="image.id"
                        class="border-stone-gray/15 group/ref bg-obsidian/60 relative aspect-square
                            overflow-hidden rounded-lg border"
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
                            @click="removeSourceImage(image.id)"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-3 w-3" />
                        </button>
                    </div>
                </div>
            </section>
        </div>

        <div
            class="border-stone-gray/10 from-anthracite/85 to-anthracite/95 sticky bottom-0 border-t
                bg-linear-to-t p-4 backdrop-blur-md"
        >
            <button
                type="button"
                class="cta-develop disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="!canSubmit"
                @click="handleSubmit"
            >
                <span class="cta-develop-bg" />
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
