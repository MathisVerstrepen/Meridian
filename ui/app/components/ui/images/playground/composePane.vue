<script lang="ts" setup>
import {
    IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH,
} from '@/stores/imagePlayground';
import {
    IMAGE_PLAYGROUND_GENERATED_IMAGE_DRAG_TYPE,
    IMAGE_PLAYGROUND_ASPECT_RATIOS,
    IMAGE_PLAYGROUND_RESOLUTIONS,
    IMAGE_PLAYGROUND_STYLE_VISUALS,
    imagePlaygroundImageUrl,
    imagePlaygroundModelIcon,
} from '@/utils/imagePlayground';
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';

const playgroundStore = useImagePlaygroundStore();
const modelStore = useModelStore();
const settingsStore = useSettingsStore();
const { error: showError, success } = useToast();
const graphEvents = useGraphEvents();
const { createImageGenerationJobs, getImageGenerationJobStatus } = useAPI();
const { isReady: modelsReady } = storeToRefs(modelStore);
const {
    isReady: settingsReady,
    toolsImageGenerationSettings,
} = storeToRefs(settingsStore);

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
    customStylePresets,
    stylePresets: availableStylePresets,
    uploadInProgress,
    variationCount,
} = storeToRefs(playgroundStore);
const {
    addSourceFiles,
    addGeneratedImageReference,
    addCustomStylePreset,
    deleteCustomStylePreset,
    applyPromptHistory,
    clearPromptHistory,
    loadCustomStylePresets,
    loadPromptHistory,
    removeSourceImage,
    removePromptHistory,
    reorderSourceImages,
    selectOnlyModel,
    setDefaultModel,
    setSourceImageReorderActive,
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
const isGeneratedReferenceDragOver = ref(false);
const isToneModalOpen = ref(false);
const newToneName = ref('');
const newToneDescription = ref('');
const newTonePrompt = ref('');
const newTonePreviewImageId = ref('');
const isGeneratingTonePreview = ref(false);
const isSavingTone = ref(false);
let tonePreviewAbortController: AbortController | null = null;
let unsubscribeCloudReferenceSelect: (() => void) | null = null;

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

const defaultImageModelId = computed(() => {
    const configuredModel = toolsImageGenerationSettings.value.defaultModel;
    return imageModels.value.find((model) => model.id === configuredModel)?.id
        || imageModels.value[0]?.id
        || '';
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
const referenceDropLabel = computed(() => {
    if (isGeneratedReferenceDragOver.value) return 'Drop to reference';
    return uploadInProgress.value ? 'Uploading…' : 'Drop or click';
});
const canSaveTone = computed(
    () => newToneName.value.trim().length > 0 && newTonePrompt.value.trim().length > 0,
);
const isCustomTonePreset = (presetId: string | number) =>
    typeof presetId === 'string' && Boolean(customStylePresets.value[presetId]);

const handleFiles = async (files: FileList | File[] | null) => {
    if (!files) return;
    const list = Array.from(files).filter((file) => file.type.startsWith('image/'));
    if (!list.length) return;
    try {
        const result = await addSourceFiles(list);
        if (result.uploaded.length) {
            success(`${result.uploaded.length} reference${result.uploaded.length > 1 ? 's' : ''} loaded.`, {
                title: 'References ready',
            });
        }
        if (result.failed) {
            showError(`${result.failed} reference${result.failed > 1 ? 's' : ''} could not be uploaded.`, {
                title: 'Some uploads failed',
            });
        }
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

const isString = (value: unknown): value is string => typeof value === 'string';

const isGeneratedImageDragPayload = (value: unknown): value is GeneratedImageGalleryItem => {
    if (!value || typeof value !== 'object') return false;
    const payload = value as Partial<GeneratedImageGalleryItem>;
    return isString(payload.id)
        && isString(payload.name)
        && isString(payload.path)
        && isString(payload.created_at)
        && isString(payload.updated_at)
        && Array.isArray(payload.source_image_ids);
};

const isGeneratedImageReferenceDrag = (event: DragEvent) =>
    Array.from(event.dataTransfer?.types || []).includes(
        IMAGE_PLAYGROUND_GENERATED_IMAGE_DRAG_TYPE,
    );

const draggedGeneratedImage = (event: DragEvent) => {
    const rawPayload = event.dataTransfer?.getData(IMAGE_PLAYGROUND_GENERATED_IMAGE_DRAG_TYPE);
    if (!rawPayload) return null;
    try {
        const payload = JSON.parse(rawPayload) as unknown;
        return isGeneratedImageDragPayload(payload) ? payload : null;
    } catch (error) {
        console.warn('Failed to parse dragged generated image:', error);
        return null;
    }
};

const addDraggedGeneratedImageReference = (event: DragEvent) => {
    if (!isGeneratedImageReferenceDrag(event)) return false;
    event.preventDefault();
    event.stopPropagation();
    isGeneratedReferenceDragOver.value = false;
    const image = draggedGeneratedImage(event);
    if (!image) return false;

    if (addGeneratedImageReference(image)) {
        success('Generated image added as a reference.', { title: 'Reference added' });
    }
    return true;
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

const onGeneratedReferenceDragEnter = (event: DragEvent) => {
    if (!isGeneratedImageReferenceDrag(event)) return;
    event.preventDefault();
    isGeneratedReferenceDragOver.value = true;
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
};

const onGeneratedReferenceDragOver = (event: DragEvent) => {
    if (!isGeneratedImageReferenceDrag(event)) return;
    event.preventDefault();
    isGeneratedReferenceDragOver.value = true;
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
};

const onGeneratedReferenceDragLeave = (event: DragEvent) => {
    if (!isGeneratedImageReferenceDrag(event)) return;
    const target = event.currentTarget;
    const relatedTarget = event.relatedTarget;
    if (
        target instanceof HTMLElement
        && relatedTarget instanceof Node
        && target.contains(relatedTarget)
    ) {
        return;
    }
    isGeneratedReferenceDragOver.value = false;
};

const onGeneratedReferenceDrop = (event: DragEvent) => {
    addDraggedGeneratedImageReference(event);
};

const onReferenceItemDragEnter = (event: DragEvent, index: number) => {
    if (isGeneratedImageReferenceDrag(event)) {
        onGeneratedReferenceDragEnter(event);
        event.stopPropagation();
        return;
    }
    if (referenceDragSourceIndex.value === null) return;
    event.preventDefault();
    event.stopPropagation();
    onReferenceDragEnter(index);
};

const onReferenceItemDragOver = (event: DragEvent) => {
    if (isGeneratedImageReferenceDrag(event)) {
        onGeneratedReferenceDragOver(event);
        event.stopPropagation();
        return;
    }
    if (referenceDragSourceIndex.value === null) return;
    event.preventDefault();
    event.stopPropagation();
};

const onReferenceItemDrop = (event: DragEvent) => {
    if (addDraggedGeneratedImageReference(event)) return;
    if (referenceDragSourceIndex.value === null) return;
    event.preventDefault();
    event.stopPropagation();
    onReferenceDragEnd();
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

const resetToneForm = () => {
    newToneName.value = '';
    newToneDescription.value = '';
    newTonePrompt.value = '';
    newTonePreviewImageId.value = '';
};

const openToneModal = () => {
    resetToneForm();
    isToneModalOpen.value = true;
};

const closeToneModal = () => {
    if (isGeneratingTonePreview.value || isSavingTone.value) return;
    isToneModalOpen.value = false;
    resetToneForm();
};

const sleep = (ms: number, signal: AbortSignal) =>
    new Promise<void>((resolve, reject) => {
        if (signal.aborted) {
            reject(new DOMException('Tone preview polling cancelled.', 'AbortError'));
            return;
        }

        const timeoutId = window.setTimeout(() => {
            signal.removeEventListener('abort', abort);
            resolve();
        }, ms);
        const abort = () => {
            window.clearTimeout(timeoutId);
            reject(new DOMException('Tone preview polling cancelled.', 'AbortError'));
        };
        signal.addEventListener('abort', abort, { once: true });
    });

const waitForTonePreviewJob = async (batchId: string, taskId: string, signal: AbortSignal) => {
    for (let attempt = 0; attempt < 60; attempt += 1) {
        if (signal.aborted) throw new DOMException('Tone preview polling cancelled.', 'AbortError');
        if (attempt > 0) await sleep(2000, signal);
        const status = await getImageGenerationJobStatus(batchId);
        if (signal.aborted) throw new DOMException('Tone preview polling cancelled.', 'AbortError');
        const task = status.tasks.find((item) => item.id === taskId);
        if (!task) continue;
        if (task.status === 'completed' && task.file_id) return task;
        if (['failed', 'cancelled'].includes(task.status)) return task;
    }
    return null;
};

const generateTonePreview = async () => {
    const tonePrompt = newTonePrompt.value.trim();
    const modelId = defaultImageModelId.value;
    if (!tonePrompt) {
        showError('Describe the tone before generating a preview.', { title: 'Tone missing' });
        return;
    }
    if (!modelId) {
        showError('No image model is available for preview generation.', { title: 'Model missing' });
        return;
    }

    isGeneratingTonePreview.value = true;
    newTonePreviewImageId.value = '';
    tonePreviewAbortController?.abort();
    const abortController = new AbortController();
    tonePreviewAbortController = abortController;
    try {
        const previewPrompt = `Generate an image illustrating this tone: ${tonePrompt}`;
        const response = await createImageGenerationJobs([
            {
                prompt: previewPrompt,
                effective_prompt: [
                    `<user_prompt>\n${previewPrompt}\n</user_prompt>`,
                    `<image_style>\n${tonePrompt}\n</image_style>`,
                    '<image_ratio>\n1:1\n</image_ratio>',
                ].join('\n\n'),
                model: modelId,
                aspect_ratio: '1:1',
                resolution: '1K',
                style_preset: null,
                source_image_ids: [],
                is_preview: true,
            },
        ]);
        const task = response.tasks[0];
        if (!task) throw new Error('Preview job was not created.');
        const completedTask = await waitForTonePreviewJob(
            response.job_id,
            task.id,
            abortController.signal,
        );
        if (!completedTask) throw new Error('Preview generation timed out.');
        if (completedTask.status !== 'completed' || !completedTask.file_id) {
            throw new Error(completedTask.error || 'Preview generation failed.');
        }
        newTonePreviewImageId.value = completedTask.file_id;
        success('Tone preview generated.', { title: 'Preview ready' });
    } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        console.error('Tone preview generation failed:', error);
        showError(error instanceof Error ? error.message : 'Could not generate tone preview.', {
            title: 'Preview failed',
        });
    } finally {
        if (tonePreviewAbortController === abortController) {
            tonePreviewAbortController = null;
            isGeneratingTonePreview.value = false;
        }
    }
};

const saveTonePreset = async () => {
    if (!canSaveTone.value) return;
    isSavingTone.value = true;
    try {
        const id = await addCustomStylePreset({
            label: newToneName.value.trim(),
            suffix: newTonePrompt.value.trim(),
            ...(newToneDescription.value.trim()
                ? { description: newToneDescription.value.trim() }
                : {}),
            ...(newTonePreviewImageId.value ? { imageId: newTonePreviewImageId.value } : {}),
        });
        stylePreset.value = id;
        success('Custom tone saved.', { title: 'Tone added' });
        isToneModalOpen.value = false;
        resetToneForm();
    } catch (error) {
        console.error('Tone save failed:', error);
        showError(error instanceof Error ? error.message : 'Could not save custom tone.', {
            title: 'Save failed',
        });
    } finally {
        isSavingTone.value = false;
    }
};

const deleteTonePreset = async (presetId: string | number, label: string) => {
    if (typeof presetId !== 'string' || !isCustomTonePreset(presetId)) return;
    if (!window.confirm(`Delete custom tone "${label}"? This cannot be undone.`)) return;

    try {
        await deleteCustomStylePreset(presetId);
        success('Custom tone deleted.', { title: 'Tone removed' });
    } catch (error) {
        console.error('Tone delete failed:', error);
        showError('Could not delete custom tone.', { title: 'Delete failed' });
    }
};

watch(
    [imageModels, () => toolsImageGenerationSettings.value.defaultModel, settingsReady],
    ([models]) => {
        setDefaultModel(models.map((model) => model.id));
    },
    { immediate: true },
);

onMounted(() => {
    loadPromptHistory();
    void loadCustomStylePresets().catch((error) => {
        console.error('Custom tone presets load failed:', error);
    });
    unsubscribeCloudReferenceSelect = graphEvents.on(
        'close-attachment-select',
        ({ nodeId, selectedFiles }) => {
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
        },
    );
});

onUnmounted(() => {
    tonePreviewAbortController?.abort();
    unsubscribeCloudReferenceSelect?.();
    unsubscribeCloudReferenceSelect = null;
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
                    <button
                        type="button"
                        class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray
                            hover:border-ember-glow/45 hover:text-ember-glow flex h-6 w-6 items-center
                            justify-center rounded-full border transition"
                        aria-label="Create tone preset"
                        @click="openToneModal"
                    >
                        <UiIcon name="Fa6SolidPlus" class="h-3 w-3" />
                    </button>
                </div>
                <div class="mt-3 grid grid-cols-3 gap-1.5">
                    <div
                        v-for="(preset, key) in availableStylePresets"
                        :key="key"
                        class="bg-anthracite/55 group/tone relative overflow-hidden rounded-xl border
                            transition hover:-translate-y-px"
                        :class="
                            stylePreset === key
                                ? 'border-ember-glow shadow-[0_0_24px_rgba(235,94,40,0.2)]'
                                : 'border-stone-gray/12 hover:border-stone-gray/35'
                        "
                    >
                        <button type="button" class="block w-full text-left" @click="stylePreset = key">
                            <span class="bg-obsidian/60 relative block h-14 w-full overflow-hidden">
                                <img
                                    v-if="preset.imageId || IMAGE_PLAYGROUND_STYLE_VISUALS[key]?.image"
                                    :src="
                                        preset.imageId
                                            ? imagePlaygroundImageUrl(preset.imageId, true)
                                            : IMAGE_PLAYGROUND_STYLE_VISUALS[key]?.image
                                    "
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
                                    {{ preset.description || IMAGE_PLAYGROUND_STYLE_VISUALS[key]?.description }}
                                </span>
                            </span>
                        </button>
                        <button
                            v-if="isCustomTonePreset(key)"
                            type="button"
                            class="absolute top-1.5 right-1.5 flex h-6 w-6 items-center justify-center
                                rounded-full bg-black/70 text-white opacity-0 transition
                                group-hover/tone:opacity-100 hover:bg-red-500/85"
                            aria-label="Delete custom tone preset"
                            @click.stop="deleteTonePreset(key, preset.label)"
                        >
                            <UiIcon name="MaterialSymbolsDeleteRounded" class="h-3.5 w-3.5" />
                        </button>
                    </div>
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

            <section
                @dragenter="onGeneratedReferenceDragEnter"
                @dragover="onGeneratedReferenceDragOver"
                @dragleave="onGeneratedReferenceDragLeave"
                @drop="onGeneratedReferenceDrop"
            >
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
                <div
                    class="mt-3 grid grid-cols-2 gap-1.5 rounded-2xl transition"
                    :class="{
                        'ring-2 ring-ember-glow/70 ring-offset-2 ring-offset-obsidian':
                            isGeneratedReferenceDragOver,
                    }"
                >
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
                            {{ referenceDropLabel }}
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
                        @dragstart.stop="onReferenceDragStart($event, index)"
                        @dragenter="onReferenceItemDragEnter($event, index)"
                        @dragover="onReferenceItemDragOver"
                        @drop="onReferenceItemDrop"
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

    <Teleport to="body">
        <div
            v-if="isToneModalOpen"
            class="bg-obsidian/80 fixed inset-0 z-100 flex items-center justify-center p-4 backdrop-blur-md"
            role="dialog"
            aria-modal="true"
            aria-label="Create tone preset"
            @click.self="closeToneModal"
        >
            <form
                class="border-stone-gray/12 bg-anthracite/95 w-full max-w-2xl overflow-hidden rounded-3xl
                    border shadow-2xl"
                @submit.prevent="saveTonePreset"
            >
                <div class="border-stone-gray/10 flex items-start justify-between gap-4 border-b p-5">
                    <div>
                        <p class="text-ember-glow font-mono text-[10px] font-bold tracking-[0.28em] uppercase">
                            Custom Tone
                        </p>
                        <h2 class="font-outfit text-soft-silk mt-2 text-2xl font-bold">
                            Save a new visual direction
                        </h2>
                        <p class="text-stone-gray mt-1 text-sm">
                            Define the tone instructions used during generation, then optionally create
                            a preview card image.
                        </p>
                    </div>
                    <button
                        type="button"
                        class="text-stone-gray hover:text-soft-silk rounded-full p-2 transition
                            disabled:opacity-40"
                        :disabled="isGeneratingTonePreview || isSavingTone"
                        aria-label="Close tone preset dialog"
                        @click="closeToneModal"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                    </button>
                </div>

                <div class="grid gap-5 p-5 md:grid-cols-[1fr_220px]">
                    <div class="space-y-4">
                        <label class="block">
                            <span class="text-stone-gray/70 text-[10px] tracking-[0.24em] uppercase">
                                Name
                            </span>
                            <input
                                v-model="newToneName"
                                class="border-stone-gray/15 bg-obsidian/60 text-soft-silk
                                    placeholder:text-stone-gray/45 mt-2 w-full rounded-xl border px-3 py-2
                                    text-sm outline-none focus:border-ember-glow/60"
                                placeholder="Noir botanical"
                                maxlength="48"
                            >
                        </label>
                        <label class="block">
                            <span class="text-stone-gray/70 text-[10px] tracking-[0.24em] uppercase">
                                Card description
                            </span>
                            <input
                                v-model="newToneDescription"
                                class="border-stone-gray/15 bg-obsidian/60 text-soft-silk
                                    placeholder:text-stone-gray/45 mt-2 w-full rounded-xl border px-3 py-2
                                    text-sm outline-none focus:border-ember-glow/60"
                                placeholder="Muted plants, hard shadows"
                                maxlength="80"
                            >
                        </label>
                        <label class="block">
                            <span class="text-stone-gray/70 text-[10px] tracking-[0.24em] uppercase">
                                Tone instructions
                            </span>
                            <textarea
                                v-model="newTonePrompt"
                                class="border-stone-gray/15 bg-obsidian/60 text-soft-silk custom_scroll
                                    placeholder:text-stone-gray/45 mt-2 min-h-36 w-full resize-none
                                    rounded-xl border px-3 py-2 text-sm leading-relaxed outline-none
                                    focus:border-ember-glow/60"
                                placeholder="Describe color, lighting, texture, composition, mood, camera language…"
                                maxlength="1200"
                            />
                        </label>
                    </div>

                    <div class="space-y-3">
                        <div
                            class="border-stone-gray/12 bg-obsidian/55 flex aspect-square items-center
                                justify-center overflow-hidden rounded-2xl border"
                        >
                            <img
                                v-if="newTonePreviewImageId"
                                :src="imagePlaygroundImageUrl(newTonePreviewImageId, true)"
                                alt="Generated tone preview"
                                class="h-full w-full object-cover"
                            >
                            <div v-else class="px-5 text-center">
                                <UiIcon
                                    :name="
                                        isGeneratingTonePreview
                                            ? 'LineMdLoadingTwotoneLoop'
                                            : 'MynauiSparklesSolid'
                                    "
                                    class="text-ember-glow mx-auto h-8 w-8"
                                />
                                <p class="text-soft-silk mt-3 text-sm font-semibold">
                                    {{ isGeneratingTonePreview ? 'Generating preview' : 'No preview yet' }}
                                </p>
                                <p class="text-stone-gray mt-1 text-xs leading-5">
                                    Uses your default image model with a square 1K request.
                                </p>
                            </div>
                        </div>
                        <button
                            type="button"
                            class="border-ember-glow/35 bg-ember-glow/8 text-ember-glow hover:bg-ember-glow/12
                                flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2
                                text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-45"
                            :disabled="isGeneratingTonePreview || !newTonePrompt.trim()"
                            @click="generateTonePreview"
                        >
                            <UiIcon
                                :name="isGeneratingTonePreview ? 'LineMdLoadingTwotoneLoop' : 'MynauiSparklesSolid'"
                                class="h-4 w-4"
                            />
                            {{ isGeneratingTonePreview ? 'Generating' : 'Generate preview' }}
                        </button>
                    </div>
                </div>

                <div class="border-stone-gray/10 flex items-center justify-end gap-2 border-t p-5">
                    <button
                        type="button"
                        class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray hover:text-soft-silk
                            rounded-xl border px-4 py-2 text-sm font-semibold transition
                            disabled:opacity-40"
                        :disabled="isGeneratingTonePreview || isSavingTone"
                        @click="closeToneModal"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        class="bg-ember-glow text-obsidian rounded-xl px-4 py-2 text-sm font-bold
                            transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45"
                        :disabled="!canSaveTone || isGeneratingTonePreview || isSavingTone"
                    >
                        {{ isSavingTone ? 'Saving' : 'Save tone' }}
                    </button>
                </div>
            </form>
        </div>
    </Teleport>
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
