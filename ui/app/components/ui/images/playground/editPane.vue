<script lang="ts" setup>
import type { GeneratedImageGalleryItem, ImageEditSelectionPayload } from '@/types/imagePlayground';
import { imagePlaygroundImageUrl, imagePlaygroundModelIcon } from '@/utils/imagePlayground';

type ImageSelection = ImageEditSelectionPayload;
type Point = { x: number; y: number };
type ResizeHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';
type EditInteraction = 'draw' | 'resize' | 'pan' | null;
type SourceSnapshot = {
    file: FileSystemObject;
    url: string;
};

const IMAGE_EDIT_CONTEXT_PADDING_PCT = 0.1;
const IMAGE_EDIT_CONTEXT_PADDING_STORAGE_KEY = 'meridian-image-edit-context-padding-percent-v2';

const modelStore = useModelStore();
const settingsStore = useSettingsStore();
const playgroundStore = useImagePlaygroundStore();
const { error: showError, success } = useToast();
const {
    isReady: settingsReady,
    toolsImageGenerationSettings,
} = storeToRefs(settingsStore);
const {
    createFolder,
    editImagePlaygroundImage,
    getFolderContents,
    getRootFolder,
    uploadFile,
} = useAPI();

const fileInputRef = ref<HTMLInputElement | null>(null);
const imageRef = ref<HTMLImageElement | null>(null);
const stageRef = ref<HTMLDivElement | null>(null);
const promptInputRef = ref<HTMLInputElement | null>(null);

const modelQuery = ref('');
const isModelMenuOpen = ref(false);
const sourceImage = ref<FileSystemObject | null>(null);
const currentImageUrl = ref('');
const reviewBeforeUrl = ref('');
const naturalSize = ref({ width: 0, height: 0 });
const selection = ref<ImageSelection | null>(null);
const draftSelection = ref<ImageSelection | null>(null);
const editPrompt = ref('');
const selectedModel = ref('');
const resolution = ref('1K');
const contextPaddingPercent = ref(IMAGE_EDIT_CONTEXT_PADDING_PCT * 100);
const pendingResult = ref<GeneratedImageGalleryItem | null>(null);
const showBefore = ref(false);
const isUploading = ref(false);
const isGenerating = ref(false);
const isDraggingFile = ref(false);
const interaction = ref<EditInteraction>(null);
const resizeHandle = ref<ResizeHandle | null>(null);
const dragAnchor = ref<Point | null>(null);
const resizeStartSelection = ref<ImageSelection | null>(null);
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const panAnchor = ref<Point | null>(null);
const panStart = ref({ x: 0, y: 0 });
const isSpacePressed = ref(false);
const undoStack = ref<SourceSnapshot[]>([]);
const redoStack = ref<SourceSnapshot[]>([]);
const objectUrls = new Set<string>();

const imageModels = computed(() =>
    modelStore.filterCompatibleModels(modelStore.filteredModels, { outputModality: 'image' }),
);
const selectedModelInfo = computed(() =>
    imageModels.value.find((model) => model.id === selectedModel.value) || imageModels.value[0] || null,
);
const visibleModels = computed(() => {
    const query = modelQuery.value.trim().toLowerCase();
    if (!query) return imageModels.value.slice(0, 80);
    return imageModels.value
        .filter((model) => model.name.toLowerCase().includes(query))
        .slice(0, 80);
});

const resolveDefaultImageModelId = () => {
    const configuredModel = toolsImageGenerationSettings.value.defaultModel;
    return imageModels.value.find((model) => model.id === configuredModel)?.id
        || imageModels.value[0]?.id
        || '';
};

const visibleSelection = computed(() => draftSelection.value || selection.value);
const isDrawing = computed(() => interaction.value === 'draw');
const displayImageUrl = computed(() =>
    showBefore.value && pendingResult.value ? reviewBeforeUrl.value : currentImageUrl.value,
);
const canGenerate = computed(
    () =>
        Boolean(sourceImage.value)
        && Boolean(selection.value)
        && Boolean(selectedModel.value)
        && !isUploading.value
        && !isGenerating.value,
);
const hasReview = computed(() => Boolean(pendingResult.value));
const zoomLabel = computed(() => `${Math.round(zoom.value * 100)}%`);
const contextPaddingPct = computed(() => contextPaddingPercent.value / 100);
const stageTransform = computed(() => ({
    transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
}));

const selectionStyle = computed(() => {
    const selected = visibleSelection.value;
    if (!selected || !naturalSize.value.width || !naturalSize.value.height) return {};
    return {
        left: `${(selected.x / naturalSize.value.width) * 100}%`,
        top: `${(selected.y / naturalSize.value.height) * 100}%`,
        width: `${(selected.width / naturalSize.value.width) * 100}%`,
        height: `${(selected.height / naturalSize.value.height) * 100}%`,
    };
});

const contextSelection = computed<ImageSelection | null>(() => {
    const selected = visibleSelection.value;
    const { width: imageWidth, height: imageHeight } = naturalSize.value;
    if (!selected || !imageWidth || !imageHeight) return null;

    const x1 = clamp(selected.x, 0, imageWidth);
    const y1 = clamp(selected.y, 0, imageHeight);
    const x2 = clamp(selected.x + selected.width, 0, imageWidth);
    const y2 = clamp(selected.y + selected.height, 0, imageHeight);
    const selectedWidth = x2 - x1;
    const selectedHeight = y2 - y1;
    if (selectedWidth <= 0 || selectedHeight <= 0) return null;

    const padX = Math.floor(selectedWidth * contextPaddingPct.value);
    const padY = Math.floor(selectedHeight * contextPaddingPct.value);
    const contextX1 = clamp(x1 - padX, 0, imageWidth);
    const contextY1 = clamp(y1 - padY, 0, imageHeight);
    const contextX2 = clamp(x2 + padX, 0, imageWidth);
    const contextY2 = clamp(y2 + padY, 0, imageHeight);

    return {
        x: contextX1,
        y: contextY1,
        width: contextX2 - contextX1,
        height: contextY2 - contextY1,
    };
});

const contextSelectionStyle = computed(() => {
    const selectedContext = contextSelection.value;
    if (!selectedContext || !naturalSize.value.width || !naturalSize.value.height) return {};
    return {
        left: `${(selectedContext.x / naturalSize.value.width) * 100}%`,
        top: `${(selectedContext.y / naturalSize.value.height) * 100}%`,
        width: `${(selectedContext.width / naturalSize.value.width) * 100}%`,
        height: `${(selectedContext.height / naturalSize.value.height) * 100}%`,
    };
});

const floatingPanelStyle = computed(() => {
    const selected = visibleSelection.value;
    if (!selected || !naturalSize.value.width || !naturalSize.value.height) return {};
    const left = Math.min(72, ((selected.x + selected.width) / naturalSize.value.width) * 100 + 2);
    const top = Math.min(78, ((selected.y + selected.height) / naturalSize.value.height) * 100 + 2);
    return { left: `${left}%`, top: `${top}%` };
});

const handlePositions: Record<ResizeHandle, string> = {
    nw: '-top-1.5 -left-1.5 cursor-nwse-resize',
    n: '-top-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize',
    ne: '-top-1.5 -right-1.5 cursor-nesw-resize',
    e: 'top-1/2 -right-1.5 -translate-y-1/2 cursor-ew-resize',
    se: '-right-1.5 -bottom-1.5 cursor-nwse-resize',
    s: '-bottom-1.5 left-1/2 -translate-x-1/2 cursor-ns-resize',
    sw: '-bottom-1.5 -left-1.5 cursor-nesw-resize',
    w: 'top-1/2 -left-1.5 -translate-y-1/2 cursor-ew-resize',
};
const resizeHandles = Object.keys(handlePositions) as ResizeHandle[];

watch(
    [imageModels, () => toolsImageGenerationSettings.value.defaultModel, settingsReady],
    () => {
        if (selectedModel.value || !settingsReady.value) return;
        selectedModel.value = resolveDefaultImageModelId();
    },
    { immediate: true },
);

watch(contextPaddingPercent, (value) => {
    contextPaddingPercent.value = clamp(Math.round(value), 0, 100);
    if (!import.meta.client) return;
    localStorage.setItem(
        IMAGE_EDIT_CONTEXT_PADDING_STORAGE_KEY,
        String(contextPaddingPercent.value),
    );
});

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const loadContextPaddingPercent = () => {
    if (!import.meta.client) return;
    const rawValue = localStorage.getItem(IMAGE_EDIT_CONTEXT_PADDING_STORAGE_KEY);
    if (rawValue === null) return;
    const storedValue = Number(rawValue);
    if (!Number.isFinite(storedValue)) return;
    contextPaddingPercent.value = clamp(Math.round(storedValue), 0, 100);
};

const makeObjectUrl = (file: File) => {
    const url = URL.createObjectURL(file);
    objectUrls.add(url);
    return url;
};

const galleryItemToFileSystemObject = (item: GeneratedImageGalleryItem): FileSystemObject => ({
    id: item.id,
    name: item.name,
    path: item.path,
    type: 'file',
    content_type: item.content_type || 'image/png',
    created_at: item.created_at,
    updated_at: item.updated_at,
    cached: false,
});

const currentSnapshot = (): SourceSnapshot | null => {
    if (!sourceImage.value || !currentImageUrl.value) return null;
    return { file: sourceImage.value, url: currentImageUrl.value };
};

const applySnapshot = (snapshot: SourceSnapshot) => {
    sourceImage.value = snapshot.file;
    currentImageUrl.value = snapshot.url;
    pendingResult.value = null;
    showBefore.value = false;
    selection.value = null;
    draftSelection.value = null;
};

const resolveUploadFolderId = async () => {
    const rootFolder = await getRootFolder();
    const defaultFolder = settingsStore.blockAttachmentSettings.default_upload_folder;
    if (!defaultFolder) return rootFolder.id;

    try {
        const contents = await getFolderContents(rootFolder.id);
        const existingFolder = contents.find(
            (file) => file.name === defaultFolder && file.type === 'folder',
        );
        if (existingFolder) return existingFolder.id;
        const folder = await createFolder(defaultFolder, rootFolder.id);
        return folder.id;
    } catch (error) {
        console.warn('Could not resolve image edit upload folder, using root:', error);
        return rootFolder.id;
    }
};

const loadImageFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
        showError('Drop or upload an image file.', { title: 'Unsupported file' });
        return;
    }

    isUploading.value = true;
    try {
        const targetFolderId = await resolveUploadFolderId();
        const uploadedFile = await uploadFile(file, targetFolderId);
        sourceImage.value = uploadedFile;
        currentImageUrl.value = makeObjectUrl(file);
        reviewBeforeUrl.value = '';
        pendingResult.value = null;
        selection.value = null;
        draftSelection.value = null;
        undoStack.value = [];
        redoStack.value = [];
        pan.value = { x: 0, y: 0 };
        zoom.value = 1;
        success('Image loaded for editing.', { title: 'Canvas ready' });
    } catch (error) {
        console.error('Image edit upload failed:', error);
        showError('Could not upload source image.', { title: 'Upload failed' });
    } finally {
        isUploading.value = false;
    }
};

const handleFiles = (files: FileList | File[] | null) => {
    const file = Array.from(files || []).find((item) => item.type.startsWith('image/'));
    if (file) void loadImageFile(file);
};

defineExpose({ handleFiles });

const onFileInputChange = (event: Event) => {
    const input = event.target as HTMLInputElement;
    handleFiles(input.files);
    input.value = '';
};

const onDrop = (event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    isDraggingFile.value = false;
    handleFiles(event.dataTransfer?.files || null);
};

const onImageLoad = () => {
    const image = imageRef.value;
    if (!image) return;
    naturalSize.value = {
        width: image.naturalWidth,
        height: image.naturalHeight,
    };
};

const imagePointFromEvent = (event: PointerEvent): Point | null => {
    const image = imageRef.value;
    if (!image || !naturalSize.value.width || !naturalSize.value.height) return null;
    const rect = image.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return {
        x: clamp(
            Math.round(((event.clientX - rect.left) / rect.width) * naturalSize.value.width),
            0,
            naturalSize.value.width,
        ),
        y: clamp(
            Math.round(((event.clientY - rect.top) / rect.height) * naturalSize.value.height),
            0,
            naturalSize.value.height,
        ),
    };
};

const normalizeSelection = (first: Point, second: Point, forceSquare: boolean): ImageSelection => {
    let end = { ...second };
    if (forceSquare) {
        const size = Math.max(Math.abs(second.x - first.x), Math.abs(second.y - first.y));
        end = {
            x: clamp(first.x + Math.sign(second.x - first.x || 1) * size, 0, naturalSize.value.width),
            y: clamp(first.y + Math.sign(second.y - first.y || 1) * size, 0, naturalSize.value.height),
        };
    }
    const x = Math.min(first.x, end.x);
    const y = Math.min(first.y, end.y);
    return {
        x,
        y,
        width: Math.abs(end.x - first.x),
        height: Math.abs(end.y - first.y),
    };
};

const selectionFromResize = (point: Point): ImageSelection | null => {
    if (!resizeStartSelection.value || !resizeHandle.value) return null;
    const start = resizeStartSelection.value;
    let left = start.x;
    let top = start.y;
    let right = start.x + start.width;
    let bottom = start.y + start.height;

    if (resizeHandle.value.includes('w')) left = point.x;
    if (resizeHandle.value.includes('e')) right = point.x;
    if (resizeHandle.value.includes('n')) top = point.y;
    if (resizeHandle.value.includes('s')) bottom = point.y;

    const x = clamp(Math.min(left, right), 0, naturalSize.value.width);
    const y = clamp(Math.min(top, bottom), 0, naturalSize.value.height);
    const width = clamp(Math.abs(right - left), 1, naturalSize.value.width - x);
    const height = clamp(Math.abs(bottom - top), 1, naturalSize.value.height - y);
    return { x, y, width, height };
};

const finishSelection = () => {
    if (draftSelection.value && draftSelection.value.width > 8 && draftSelection.value.height > 8) {
        selection.value = draftSelection.value;
        nextTick(() => promptInputRef.value?.focus());
    }
    draftSelection.value = null;
    interaction.value = null;
    resizeHandle.value = null;
    dragAnchor.value = null;
    resizeStartSelection.value = null;
};

const startPan = (event: PointerEvent) => {
    interaction.value = 'pan';
    panAnchor.value = { x: event.clientX, y: event.clientY };
    panStart.value = { ...pan.value };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
};

const onStagePointerDown = (event: PointerEvent) => {
    if (!sourceImage.value || hasReview.value || isGenerating.value) return;
    if (isSpacePressed.value || event.button === 1) {
        event.preventDefault();
        startPan(event);
        return;
    }
    const point = imagePointFromEvent(event);
    if (!point) return;
    interaction.value = 'draw';
    dragAnchor.value = point;
    draftSelection.value = { x: point.x, y: point.y, width: 1, height: 1 };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
};

const startResize = (handle: ResizeHandle, event: PointerEvent) => {
    if (!selection.value || hasReview.value || isGenerating.value) return;
    const point = imagePointFromEvent(event);
    if (!point) return;
    event.preventDefault();
    interaction.value = 'resize';
    resizeHandle.value = handle;
    resizeStartSelection.value = selection.value;
    draftSelection.value = selection.value;
    const target = stageRef.value || (event.currentTarget as HTMLElement);
    target.setPointerCapture(event.pointerId);
};

const onStagePointerMove = (event: PointerEvent) => {
    if (interaction.value === 'pan' && panAnchor.value) {
        pan.value = {
            x: panStart.value.x + event.clientX - panAnchor.value.x,
            y: panStart.value.y + event.clientY - panAnchor.value.y,
        };
        return;
    }

    const point = imagePointFromEvent(event);
    if (!point) return;
    if (interaction.value === 'draw' && dragAnchor.value) {
        draftSelection.value = normalizeSelection(dragAnchor.value, point, event.shiftKey);
    }
    if (interaction.value === 'resize') {
        draftSelection.value = selectionFromResize(point);
    }
};

const onStagePointerEnd = (event: PointerEvent) => {
    if (stageRef.value?.hasPointerCapture(event.pointerId)) {
        stageRef.value.releasePointerCapture(event.pointerId);
    }
    if (interaction.value === 'draw' || interaction.value === 'resize') {
        finishSelection();
        return;
    }
    interaction.value = null;
    panAnchor.value = null;
};

const onWheel = (event: WheelEvent) => {
    if (!sourceImage.value) return;
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.08 : 0.08;
    zoom.value = clamp(Number((zoom.value + delta).toFixed(2)), 0.35, 3);
};

const clearSelection = () => {
    isModelMenuOpen.value = false;
    selection.value = null;
    draftSelection.value = null;
    pendingResult.value = null;
    showBefore.value = false;
    if (reviewBeforeUrl.value) currentImageUrl.value = reviewBeforeUrl.value;
    reviewBeforeUrl.value = '';
};

const resetFields = () => {
    isModelMenuOpen.value = false;
    sourceImage.value = null;
    currentImageUrl.value = '';
    reviewBeforeUrl.value = '';
    naturalSize.value = { width: 0, height: 0 };
    selection.value = null;
    draftSelection.value = null;
    editPrompt.value = '';
    selectedModel.value = resolveDefaultImageModelId();
    resolution.value = '1K';
    contextPaddingPercent.value = IMAGE_EDIT_CONTEXT_PADDING_PCT * 100;
    pendingResult.value = null;
    showBefore.value = false;
    isDraggingFile.value = false;
    interaction.value = null;
    resizeHandle.value = null;
    dragAnchor.value = null;
    resizeStartSelection.value = null;
    zoom.value = 1;
    pan.value = { x: 0, y: 0 };
    panAnchor.value = null;
    panStart.value = { x: 0, y: 0 };
    isSpacePressed.value = false;
    undoStack.value = [];
    redoStack.value = [];
    modelQuery.value = '';
};

const selectModel = (modelId: string) => {
    selectedModel.value = modelId;
    isModelMenuOpen.value = false;
};

const handleGenerate = async () => {
    if (!canGenerate.value || !sourceImage.value || !selection.value) return;
    isModelMenuOpen.value = false;
    isGenerating.value = true;
    reviewBeforeUrl.value = currentImageUrl.value;
    pendingResult.value = null;
    showBefore.value = false;
    try {
        const result = await editImagePlaygroundImage({
            source_image_id: sourceImage.value.id,
            prompt: editPrompt.value.trim(),
            model: selectedModel.value,
            selection: {
                x: Math.round(selection.value.x),
                y: Math.round(selection.value.y),
                width: Math.round(selection.value.width),
                height: Math.round(selection.value.height),
            },
            resolution: resolution.value,
            padding_pct: contextPaddingPct.value,
        });
        pendingResult.value = result;
        currentImageUrl.value = imagePlaygroundImageUrl(result.id);
        void playgroundStore.loadGallery();
        success('Edit blended back into image.', { title: 'Review result' });
    } catch (error) {
        console.error('Image edit failed:', error);
        currentImageUrl.value = reviewBeforeUrl.value;
        showError('Could not complete image edit.', { title: 'Edit failed' });
    } finally {
        isGenerating.value = false;
    }
};

const acceptResult = () => {
    if (!pendingResult.value) return;
    const previous = sourceImage.value && reviewBeforeUrl.value
        ? { file: sourceImage.value, url: reviewBeforeUrl.value }
        : currentSnapshot();
    if (previous) undoStack.value = [...undoStack.value, previous];
    redoStack.value = [];
    sourceImage.value = galleryItemToFileSystemObject(pendingResult.value);
    currentImageUrl.value = imagePlaygroundImageUrl(pendingResult.value.id);
    pendingResult.value = null;
    reviewBeforeUrl.value = '';
    showBefore.value = false;
    selection.value = null;
    success('Edit accepted.', { title: 'Canvas updated' });
};

const rejectResult = () => {
    if (reviewBeforeUrl.value) currentImageUrl.value = reviewBeforeUrl.value;
    pendingResult.value = null;
    reviewBeforeUrl.value = '';
    showBefore.value = false;
};

const regenerateResult = () => {
    if (reviewBeforeUrl.value) currentImageUrl.value = reviewBeforeUrl.value;
    pendingResult.value = null;
    void handleGenerate();
};

const undo = () => {
    const previous = undoStack.value.at(-1);
    const current = currentSnapshot();
    if (!previous || !current) return;
    undoStack.value = undoStack.value.slice(0, -1);
    redoStack.value = [...redoStack.value, current];
    applySnapshot(previous);
};

const redo = () => {
    const next = redoStack.value.at(-1);
    const current = currentSnapshot();
    if (!next || !current) return;
    redoStack.value = redoStack.value.slice(0, -1);
    undoStack.value = [...undoStack.value, current];
    applySnapshot(next);
};

const exportImage = () => {
    if (!currentImageUrl.value) return;
    const link = document.createElement('a');
    link.href = currentImageUrl.value;
    link.download = `${crypto.randomUUID()}.png`;
    link.click();
};

const isEditableShortcutTarget = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) return false;
    return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
};

const handleKeydown = (event: KeyboardEvent) => {
    if (isEditableShortcutTarget(event.target)) return;

    if (event.code === 'Space') isSpacePressed.value = true;
    if (event.key === 'Escape') clearSelection();
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
    }
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        void handleGenerate();
    }
};

const handleKeyup = (event: KeyboardEvent) => {
    if (event.code === 'Space') isSpacePressed.value = false;
};

onMounted(() => {
    loadContextPaddingPercent();
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('keyup', handleKeyup);
});

onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleKeydown);
    window.removeEventListener('keyup', handleKeyup);
    objectUrls.forEach((url) => URL.revokeObjectURL(url));
});
</script>

<template>
    <main
        class="border-stone-gray/12 bg-obsidian/45 relative flex min-h-0 flex-1 overflow-hidden
            rounded-[2rem] border shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
        @dragenter.prevent="isDraggingFile = true"
        @dragover.prevent="isDraggingFile = true"
        @dragleave="isDraggingFile = false"
        @drop="onDrop"
    >
        <input
            ref="fileInputRef"
            class="hidden"
            type="file"
            accept="image/*"
            @change="onFileInputChange"
        >

        <div
            class="border-stone-gray/10 bg-obsidian/70 absolute top-4 right-4 left-4 z-20 flex
                items-center justify-between rounded-2xl border px-3 py-2 backdrop-blur-xl"
        >
            <div class="flex items-center gap-2">
                <button
                    type="button"
                    class="bg-soft-silk text-obsidian hover:bg-ember-glow rounded-xl px-3 py-2 text-xs
                        font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="isUploading"
                    @click="fileInputRef?.click()"
                >
                    {{ sourceImage ? 'Upload New Image' : 'Upload Image' }}
                </button>
                <button
                    type="button"
                    class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray hover:border-ember-glow/45
                        hover:text-ember-glow flex items-center gap-1.5 rounded-xl border px-3 py-2
                        text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-35"
                    :disabled="isUploading || isGenerating"
                    title="Reset all fields"
                    @click="resetFields"
                >
                    <UiIcon name="MaterialSymbolsRefreshRounded" class="h-3.5 w-3.5" />
                    Reset
                </button>
                <button
                    type="button"
                    class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray hover:text-soft-silk
                        rounded-xl border px-2 py-1 transition disabled:cursor-not-allowed disabled:opacity-35"
                    :disabled="!undoStack.length"
                    title="Undo"
                    @click="undo"
                >
                    <UiIcon name="MaterialSymbolsUndoRounded" class="h-4 w-4" />
                </button>
                <button
                    type="button"
                    class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray hover:text-soft-silk
                        rounded-xl border px-2 py-1 transition disabled:cursor-not-allowed disabled:opacity-35"
                    :disabled="!redoStack.length"
                    title="Redo"
                    @click="redo"
                >
                    <UiIcon name="MaterialSymbolsRedoRounded" class="h-4 w-4" />
                </button>
            </div>

            <div class="flex items-center gap-2">
                <span class="text-stone-gray font-mono text-xs">{{ zoomLabel }}</span>
                <button
                    type="button"
                    class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray hover:text-soft-silk
                        rounded-xl border px-3 py-2 text-xs font-semibold transition disabled:opacity-35"
                    :disabled="!sourceImage"
                    @click="exportImage"
                >
                    Export
                </button>
            </div>
        </div>

        <section
            ref="stageRef"
            class="relative flex min-h-0 flex-1 cursor-crosshair items-center justify-center overflow-hidden
                pt-20"
            :class="{ 'cursor-grab': isSpacePressed || interaction === 'pan' }"
            @pointerdown="onStagePointerDown"
            @pointermove="onStagePointerMove"
            @pointerup="onStagePointerEnd"
            @pointercancel="onStagePointerEnd"
            @wheel="onWheel"
        >
            <div
                v-if="!sourceImage"
                class="border-stone-gray/16 bg-soft-silk/4 mx-8 flex w-full max-w-3xl flex-col
                    items-center justify-center rounded-[2rem] border border-dashed p-12 text-center"
            >
                <UiIcon name="MdiImageEditOutline" class="text-ember-glow h-12 w-12" />
                <h2 class="font-outfit text-soft-silk mt-5 text-3xl font-bold">
                    Drop an image to begin editing.
                </h2>
                <p class="text-stone-gray mt-3 max-w-md text-sm leading-6">
                    Draw a box over the area to change. The backend crops around the selection,
                    asks the model for the edit, then composites only masked pixels back in.
                </p>
                <button
                    type="button"
                    class="bg-ember-glow text-obsidian mt-6 rounded-full px-5 py-2.5 text-xs
                        font-bold tracking-[0.18em] uppercase transition hover:brightness-110"
                    @click="fileInputRef?.click()"
                >
                    Choose image
                </button>
            </div>

            <div
                v-else
                class="relative max-h-[calc(100vh-11rem)] max-w-[calc(100vw-5rem)] origin-center
                    transition-transform duration-150"
                :style="stageTransform"
            >
                <img
                    ref="imageRef"
                    :src="displayImageUrl"
                    class="max-h-[calc(100vh-11rem)] max-w-[calc(100vw-5rem)] select-none rounded-xl
                        object-contain shadow-2xl"
                    draggable="false"
                    alt="Image edit source"
                    @load="onImageLoad"
                >

                <div
                    v-if="visibleSelection"
                    class="pointer-events-none absolute inset-0 rounded-xl bg-black/30"
                    aria-hidden="true"
                />
                <div
                    v-if="contextSelection"
                    class="border-ember-glow/55 bg-ember-glow/8 pointer-events-none absolute z-10
                        rounded-[14px] border border-dashed shadow-[0_0_0_1px_rgba(235,94,40,0.18),0_0_30px_-16px_rgba(235,94,40,0.8)]"
                    :style="contextSelectionStyle"
                >
                    <span
                        class="bg-obsidian/85 text-ember-glow border-ember-glow/30 absolute -top-6 left-2
                            rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold tracking-[0.16em]
                            uppercase shadow-lg"
                    >
                        Context
                    </span>
                </div>
                <div
                    v-if="visibleSelection"
                    class="pointer-events-none absolute z-20 rounded-[10px] border border-dashed
                        border-white/90 shadow-[0_0_0_1px_rgba(235,94,40,0.75),0_0_24px_-12px_rgba(255,255,255,0.9)]"
                    :class="{ 'editing-selection-pulse': isGenerating }"
                    :style="selectionStyle"
                >
                    <span
                        class="bg-soft-silk text-obsidian absolute -top-6 left-2 rounded-full px-2 py-0.5
                            font-mono text-[10px] font-bold tracking-[0.16em] uppercase shadow-lg"
                    >
                        Edit mask
                    </span>
                    <div
                        v-if="isGenerating"
                        class="editing-overlay"
                        aria-hidden="true"
                    >
                        <div class="editing-scan-beam" />
                        <span class="editing-corner editing-corner-tl" />
                        <span class="editing-corner editing-corner-tr" />
                        <span class="editing-corner editing-corner-bl" />
                        <span class="editing-corner editing-corner-br" />
                    </div>
                    <button
                        v-for="handle in resizeHandles"
                        :key="handle"
                        type="button"
                        class="pointer-events-auto absolute h-3 w-3 rounded-full border border-obsidian
                            bg-soft-silk shadow-lg transition hover:scale-125"
                        :class="handlePositions[handle]"
                        :disabled="hasReview || isGenerating"
                        @pointerdown.stop="startResize(handle, $event)"
                    />
                </div>

                <div
                    v-if="selection && !isDrawing"
                    class="border-stone-gray/12 bg-obsidian/90 absolute z-30 w-[340px] rounded-2xl border
                        p-3 shadow-2xl backdrop-blur-xl"
                    :style="floatingPanelStyle"
                    @pointerdown.stop
                >
                    <template v-if="!hasReview">
                        <div class="flex items-center gap-2">
                            <input
                                ref="promptInputRef"
                                v-model="editPrompt"
                                class="border-stone-gray/12 bg-soft-silk/6 text-soft-silk placeholder:text-stone-gray/60
                                    h-10 min-w-0 flex-1 rounded-xl border px-3 text-sm outline-none
                                    focus:border-ember-glow/45"
                                placeholder="What do you want to see here?"
                                @keydown.enter.prevent="handleGenerate"
                            >
                            <button
                                type="button"
                                class="bg-ember-glow text-obsidian h-10 rounded-xl px-4 text-xs font-bold
                                    transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45"
                                :disabled="!canGenerate"
                                @click="handleGenerate"
                            >
                                {{ isGenerating ? 'Working' : 'Generate' }}
                            </button>
                        </div>
                        <div class="mt-2 grid grid-cols-[1fr_auto] gap-2">
                            <div class="relative min-w-0">
                                <button
                                    type="button"
                                    class="border-stone-gray/12 bg-soft-silk/6 text-soft-silk flex h-9 w-full
                                        items-center gap-2 rounded-xl border px-2 text-left text-[11px]
                                        outline-none transition hover:border-stone-gray/32"
                                    @click="isModelMenuOpen = !isModelMenuOpen"
                                >
                                    <span
                                        class="border-stone-gray/15 bg-obsidian/70 flex h-6 w-6 shrink-0
                                            items-center justify-center rounded-lg border"
                                    >
                                        <UiIcon
                                            v-if="selectedModelInfo"
                                            :name="imagePlaygroundModelIcon(selectedModelInfo)"
                                            class="h-3.5 w-3.5"
                                            :title="selectedModelInfo.provider"
                                        />
                                    </span>
                                    <span class="min-w-0 flex-1 truncate font-semibold">
                                        {{ selectedModelInfo?.name || 'Select model' }}
                                    </span>
                                    <UiIcon
                                        name="FlowbiteChevronDownOutline"
                                        class="text-stone-gray h-4 w-4 shrink-0 transition"
                                        :class="{ 'rotate-180': isModelMenuOpen }"
                                    />
                                </button>
                                <div
                                    v-if="isModelMenuOpen"
                                    class="border-stone-gray/12 bg-obsidian/95 absolute right-0 bottom-11 z-50
                                        w-[320px] rounded-2xl border p-2 shadow-2xl backdrop-blur-xl"
                                    @wheel.stop
                                >
                                    <div class="relative">
                                        <UiIcon
                                            name="MdiMagnify"
                                            class="text-stone-gray/50 absolute top-1/2 left-3 h-4 w-4
                                                -translate-y-1/2"
                                        />
                                        <input
                                            v-model="modelQuery"
                                            class="border-stone-gray/15 bg-obsidian/60 focus:border-ember-glow/60
                                                placeholder:text-stone-gray/45 w-full rounded-xl border px-3
                                                py-1.5 pl-9 text-sm outline-none"
                                            placeholder="Filter image models…"
                                            @keydown.escape="isModelMenuOpen = false"
                                        >
                                    </div>
                                    <div
                                        class="custom_scroll hover_scrollbar_y mt-2 grid max-h-56 grid-cols-3
                                            gap-1.5 overflow-y-auto pt-0.5 pr-1"
                                    >
                                        <button
                                            v-for="model in visibleModels"
                                            :key="model.id"
                                            type="button"
                                            class="relative flex min-h-22 flex-col items-center justify-between
                                                gap-2 rounded-xl border p-2.5 text-center text-xs transition
                                                hover:-translate-y-px"
                                            :class="
                                                selectedModel === model.id
                                                    ? `border-ember-glow bg-ember-glow/12 text-ember-glow
                                                        shadow-[inset_0_0_0_1px_rgba(235,94,40,0.2),0_0_28px_-8px_rgba(235,94,40,0.45)]`
                                                    : `border-stone-gray/12 bg-soft-silk/4 text-soft-silk/80
                                                        hover:border-stone-gray/32`
                                            "
                                            @click="selectModel(model.id)"
                                        >
                                            <span
                                                v-if="selectedModel === model.id"
                                                class="bg-ember-glow absolute top-2 right-2 h-1.5 w-1.5
                                                    rounded-full shadow-[0_0_10px_rgba(235,94,40,0.9)]"
                                            />
                                            <span
                                                class="border-stone-gray/15 bg-obsidian/70 flex h-9 w-9
                                                    items-center justify-center rounded-lg border transition"
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
                                </div>
                            </div>
                            <button
                                type="button"
                                class="border-stone-gray/12 bg-soft-silk/5 text-stone-gray hover:text-soft-silk
                                    rounded-xl border px-3 text-[11px] font-semibold transition"
                                @click="clearSelection"
                            >
                                Clear
                            </button>
                        </div>
                    </template>
                    <template v-else>
                        <div class="grid grid-cols-4 gap-2">
                            <button
                                type="button"
                                class="bg-ember-glow text-obsidian rounded-xl py-2 text-xs font-bold"
                                @click="acceptResult"
                            >
                                Accept
                            </button>
                            <button
                                type="button"
                                class="border-red-400/25 bg-red-500/10 text-red-200 rounded-xl border py-2
                                    text-xs font-bold"
                                @click="rejectResult"
                            >
                                Reject
                            </button>
                            <button
                                type="button"
                                class="border-stone-gray/12 bg-soft-silk/5 text-soft-silk rounded-xl border
                                    py-2 text-xs font-bold"
                                :disabled="isGenerating"
                                @click="regenerateResult"
                            >
                                Regen
                            </button>
                            <button
                                type="button"
                                class="border-stone-gray/12 bg-soft-silk/5 text-soft-silk rounded-xl border
                                    py-2 text-xs font-bold"
                                @mousedown="showBefore = true"
                                @mouseup="showBefore = false"
                                @mouseleave="showBefore = false"
                            >
                                Before
                            </button>
                        </div>
                    </template>
                </div>
            </div>

            <div
                v-if="sourceImage && !selection && !isGenerating && !hasReview"
                class="border-stone-gray/12 bg-obsidian/70 text-stone-gray pointer-events-none absolute
                    top-24 left-1/2 z-10 -translate-x-1/2 rounded-full border px-4 py-2 text-xs
                    tracking-[0.18em] uppercase backdrop-blur-xl"
            >
                Click and drag to select an area. Hold Shift for square.
            </div>
        </section>

        <aside
            class="border-stone-gray/10 bg-obsidian/75 hidden w-72 shrink-0 border-l p-4 pt-24
                backdrop-blur-xl xl:block"
        >
            <p class="text-ember-glow text-xs font-semibold tracking-[0.35em] uppercase">Image Edit</p>
            <h2 class="font-outfit text-soft-silk mt-3 text-2xl font-bold">Box-select editor</h2>
            <div class="mt-5 space-y-4 text-sm">
                <div class="border-stone-gray/10 bg-soft-silk/4 rounded-2xl border p-3">
                    <p class="text-stone-gray text-xs uppercase tracking-[0.2em]">Model</p>
                    <div class="mt-3 flex items-center gap-2">
                        <UiIcon
                            v-if="selectedModelInfo"
                            :name="imagePlaygroundModelIcon(selectedModelInfo)"
                            class="text-soft-silk h-5 w-5"
                        />
                        <p class="text-soft-silk truncate text-sm font-semibold">
                            {{ selectedModelInfo?.name || 'No model' }}
                        </p>
                    </div>
                </div>
                <div class="border-stone-gray/10 bg-soft-silk/4 rounded-2xl border p-3">
                    <p class="text-stone-gray text-xs uppercase tracking-[0.2em]">Selection</p>
                    <p v-if="selection" class="text-soft-silk mt-2 font-mono text-xs">
                        {{ selection.width }} × {{ selection.height }} px
                    </p>
                    <p v-else class="text-stone-gray mt-2 text-xs">No box selected.</p>
                </div>
                <div class="border-stone-gray/10 bg-soft-silk/4 rounded-2xl border p-3">
                    <div class="flex items-center justify-between gap-3">
                        <p class="text-stone-gray text-xs uppercase tracking-[0.2em]">Context padding</p>
                        <p class="text-ember-glow font-mono text-xs font-bold">
                            {{ contextPaddingPercent }}%
                        </p>
                    </div>
                    <input
                        v-model.number="contextPaddingPercent"
                        type="range"
                        min="0"
                        max="100"
                        step="5"
                        class="iteration-slider mt-4 w-full"
                        :style="{ '--iteration-progress': `${contextPaddingPercent}%` }"
                    >
                    <div class="text-stone-gray/70 mt-2 flex justify-between font-mono text-[10px]">
                        <span>Tight</span>
                        <span>Wide</span>
                    </div>
                    <p class="text-stone-gray mt-3 text-xs leading-5">
                        Controls visible padding around the edit mask. The edit mask stays exact.
                    </p>
                </div>
            </div>
        </aside>

        <div
            v-if="isDraggingFile"
            class="bg-obsidian/85 border-ember-glow/30 absolute inset-4 z-40 flex items-center
                justify-center rounded-[2rem] border border-dashed text-center backdrop-blur-sm"
        >
            <div>
                <UiIcon name="MdiImagePlusOutline" class="text-ember-glow mx-auto h-12 w-12" />
                <p class="text-soft-silk mt-4 text-lg font-bold">Drop image to load editor</p>
            </div>
        </div>
    </main>
</template>
