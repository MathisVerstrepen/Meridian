import { defineStore } from 'pinia';
import type {
    GeneratedImageGalleryItem,
    ImageGalleryFilters,
    ImageGalleryReferenceFilter,
    ImageGenerationJob,
    ImageGenerationTaskPayload,
    VideoGenerationPayload,
} from '@/types/imagePlayground';

type StylePreset = {
    label: string;
    suffix: string;
};

export const IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH = 24;
const IMAGE_PROMPT_HISTORY_MAX_ITEMS = 24;
const IMAGE_PROMPT_HISTORY_STORAGE_KEY = 'meridian-image-playground-prompt-history';
const ACTIVE_JOBS_SYNC_INTERVAL_MS = 30000;

export const IMAGE_STYLE_PRESETS: Record<string, StylePreset> = {
    none: { label: 'None', suffix: '' },
    photorealistic: {
        label: 'Photorealistic',
        suffix: 'photorealistic, natural light, high fidelity, sharp focus',
    },
    cinematic: {
        label: 'Cinematic',
        suffix: 'cinematic lighting, dramatic composition, highly detailed, film still',
    },
    anime: {
        label: 'Anime',
        suffix: 'anime style, expressive character design, clean line art, vibrant colors',
    },
    render3d: {
        label: '3D Render',
        suffix: '3D render, octane lighting, polished materials, high detail',
    },
    cyberpunk: {
        label: 'Cyberpunk',
        suffix: 'cyberpunk neon, rainy city, high contrast, futuristic atmosphere',
    },
};

export const useImagePlaygroundStore = defineStore('ImagePlayground', () => {
    const settingsStore = useSettingsStore();
    const prompt = ref('');
    const selectedModels = ref<string[]>([]);
    const aspectRatio = ref('1:1');
    const resolution = ref('1K');
    const stylePreset = ref('none');
    const variationCount = ref(1);
    const sourceImages = ref<FileSystemObject[]>([]);
    const isReorderingSourceImages = ref(false);
    const promptHistory = ref<string[]>([]);
    const gallerySearchQuery = ref('');
    const galleryModelFilter = ref('');
    const galleryAspectFilter = ref('');
    const galleryReferenceFilter = ref<ImageGalleryReferenceFilter>('all');
    const gallery = ref<GeneratedImageGalleryItem[]>([]);
    const galleryTotal = ref(0);
    const activeJobs = ref<ImageGenerationJob[]>([]);
    const activeBatchIds = ref<string[]>([]);
    const isSubmitting = ref(false);
    const isLoadingGallery = ref(false);
    const isLoadingMoreGallery = ref(false);
    const hasMoreGallery = ref(false);
    const uploadInProgress = ref(false);
    const lastError = ref<string | null>(null);

    const galleryPageSize = 40;
    const galleryOffset = ref(0);
    let activeJobsSyncTimer: ReturnType<typeof setInterval> | null = null;
    let activeJobsSyncInFlight = false;

    const {
        clearFailedImageGenerationJobs,
        cancelImageGenerationJob,
        createImageGenerationJobs,
        deleteFileSystemObject,
        dismissImageGenerationJob,
        getActiveImageGenerationJobs,
        getFolderContents,
        getImagePlaygroundGallery,
        getRootFolder,
        createFolder,
        retryImageGenerationJob,
        createVideoGenerationJobs,
        uploadFile,
    } = useAPI();
    const { connect: connectWebSocket, isConnected: isWebSocketConnected } = useWebSocket();

    const selectedStyle = computed(() => IMAGE_STYLE_PRESETS[stylePreset.value] ?? IMAGE_STYLE_PRESETS.none);

    const sourceImageIds = computed(() => sourceImages.value.map((image) => image.id));

    const galleryFilters = computed<ImageGalleryFilters>(() => ({
        search: gallerySearchQuery.value,
        model: galleryModelFilter.value || undefined,
        aspect_ratio: galleryAspectFilter.value || undefined,
        references: galleryReferenceFilter.value,
    }));

    const activeGalleryFilterCount = computed(
        () =>
            (gallerySearchQuery.value.trim() ? 1 : 0) +
            (galleryModelFilter.value ? 1 : 0) +
            (galleryAspectFilter.value ? 1 : 0) +
            (galleryReferenceFilter.value !== 'all' ? 1 : 0),
    );

    const generationCount = computed(
        () => Math.max(1, variationCount.value) * selectedModels.value.length,
    );
    const exceedsBatchLimit = computed(
        () => generationCount.value > IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH,
    );

    const effectivePromptFor = (rawPrompt: string) => {
        const trimmedPrompt = rawPrompt.trim();
        const suffix = selectedStyle.value.suffix.trim();
        const promptSections = [`<user_prompt>\n${trimmedPrompt}\n</user_prompt>`];

        if (suffix) {
            promptSections.push(`<image_style>\n${suffix}\n</image_style>`);
        }

        promptSections.push(`<image_ratio>\n${aspectRatio.value}\n</image_ratio>`);

        return promptSections.join('\n\n');
    };

    const setDefaultModel = (modelId: string) => {
        if (selectedModels.value.length === 0 && modelId) {
            selectedModels.value = [modelId];
        }
    };

    const toggleModel = (modelId: string) => {
        if (selectedModels.value.includes(modelId)) {
            selectedModels.value = selectedModels.value.filter((id) => id !== modelId);
            return;
        }
        selectedModels.value = [...selectedModels.value, modelId];
    };

    const selectOnlyModel = (modelId: string) => {
        selectedModels.value = modelId ? [modelId] : [];
    };

    const savePromptHistory = () => {
        if (!import.meta.client) return;
        try {
            localStorage.setItem(IMAGE_PROMPT_HISTORY_STORAGE_KEY, JSON.stringify(promptHistory.value));
        } catch (error) {
            console.warn('Failed to save image prompt history:', error);
        }
    };

    const loadPromptHistory = () => {
        if (!import.meta.client) return;
        try {
            const storedHistory = localStorage.getItem(IMAGE_PROMPT_HISTORY_STORAGE_KEY);
            if (!storedHistory) return;
            const parsedHistory = JSON.parse(storedHistory) as unknown[];
            if (!Array.isArray(parsedHistory)) return;

            const historyPrompts = parsedHistory
                .map((entry) => {
                    if (typeof entry === 'string') return entry.trim();
                    if (entry && typeof entry === 'object' && 'prompt' in entry) {
                        return String(entry.prompt).trim();
                    }
                    return '';
                })
                .filter(Boolean);

            promptHistory.value = [...new Set(historyPrompts)].slice(0, IMAGE_PROMPT_HISTORY_MAX_ITEMS);
            savePromptHistory();
        } catch (error) {
            console.warn('Failed to load image prompt history:', error);
            localStorage.removeItem(IMAGE_PROMPT_HISTORY_STORAGE_KEY);
        }
    };

    const addPromptHistory = () => {
        const trimmedPrompt = prompt.value.trim();
        if (!trimmedPrompt) return;

        promptHistory.value = [
            trimmedPrompt,
            ...promptHistory.value.filter((item) => item.trim() !== trimmedPrompt),
        ].slice(0, IMAGE_PROMPT_HISTORY_MAX_ITEMS);
        savePromptHistory();
    };

    const applyPromptHistory = (historyPrompt: string) => {
        prompt.value = historyPrompt;
    };

    const removePromptHistory = (historyPrompt: string) => {
        promptHistory.value = promptHistory.value.filter((entry) => entry !== historyPrompt);
        savePromptHistory();
    };

    const clearPromptHistory = () => {
        promptHistory.value = [];
        savePromptHistory();
    };

    const buildTasks = (): ImageGenerationTaskPayload[] => {
        const models = selectedModels.value.filter(Boolean);
        if (!models.length) {
            throw new Error('Select at least one image model.');
        }

        const trimmedPrompt = prompt.value.trim();
        if (!trimmedPrompt) {
            throw new Error('Prompt is required.');
        }

        const tasks = models.flatMap((model) =>
            Array.from({ length: Math.max(1, variationCount.value) }, () => ({
                prompt: trimmedPrompt,
                effective_prompt: effectivePromptFor(trimmedPrompt),
                model,
                aspect_ratio: aspectRatio.value,
                resolution: resolution.value,
                style_preset: stylePreset.value === 'none' ? null : stylePreset.value,
                source_image_ids: sourceImageIds.value,
            })),
        );

        if (tasks.length > IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH) {
            throw new Error(
                `Maximum ${IMAGE_PLAYGROUND_MAX_TASKS_PER_BATCH} images per batch. `
                    + 'Reduce models or iterations.',
            );
        }

        return tasks;
    };

    const mergeGalleryPage = (items: GeneratedImageGalleryItem[], append: boolean) => {
        if (!append) {
            gallery.value = items;
            return;
        }

        const existingIds = new Set(gallery.value.map((image) => image.id));
        gallery.value = [...gallery.value, ...items.filter((image) => !existingIds.has(image.id))];
    };

    const loadGallery = async () => {
        isLoadingGallery.value = true;
        try {
            const response = await getImagePlaygroundGallery(
                galleryPageSize,
                0,
                galleryFilters.value,
            );
            mergeGalleryPage(response.items, false);
            galleryTotal.value = response.total;
            galleryOffset.value = response.items.length;
            hasMoreGallery.value = galleryOffset.value < response.total;
        } finally {
            isLoadingGallery.value = false;
        }
    };

    const loadMoreGallery = async () => {
        if (isLoadingMoreGallery.value || !hasMoreGallery.value) return;
        isLoadingMoreGallery.value = true;
        try {
            const response = await getImagePlaygroundGallery(
                galleryPageSize,
                galleryOffset.value,
                galleryFilters.value,
            );
            mergeGalleryPage(response.items, true);
            galleryTotal.value = response.total;
            galleryOffset.value += response.items.length;
            hasMoreGallery.value = galleryOffset.value < response.total;
        } finally {
            isLoadingMoreGallery.value = false;
        }
    };

    const galleryItemMatchesFilters = (image: GeneratedImageGalleryItem) => {
        const searchQuery = gallerySearchQuery.value.trim().toLowerCase();
        if (searchQuery) {
            const searchableText = [image.name, image.prompt, image.effective_prompt]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            if (!searchableText.includes(searchQuery)) return false;
        }
        if (galleryModelFilter.value && image.model !== galleryModelFilter.value) return false;
        if (galleryAspectFilter.value) {
            const displayedAspectRatio = image.actual_aspect_ratio || image.aspect_ratio;
            if (displayedAspectRatio !== galleryAspectFilter.value) return false;
        }
        if (galleryReferenceFilter.value === 'with' && !image.source_image_ids.length) return false;
        if (galleryReferenceFilter.value === 'without' && image.source_image_ids.length) return false;
        return true;
    };

    const clearGalleryFilters = () => {
        gallerySearchQuery.value = '';
        galleryModelFilter.value = '';
        galleryAspectFilter.value = '';
        galleryReferenceFilter.value = 'all';
    };

    const prependCompletedJobs = (jobs: ImageGenerationJob[]) => {
        const visibleGalleryIds = new Set(gallery.value.map((image) => image.id));
        const completedImages = jobs
            .filter(
                (job) =>
                    job.media_type !== 'video' &&
                    job.status === 'completed' &&
                    job.file_id &&
                    !visibleGalleryIds.has(job.file_id),
            )
            .map((job) => {
                const createdAt = job.completed_at || job.updated_at || job.created_at;
                return {
                    id: job.file_id as string,
                    name: `Gen: ${job.prompt.slice(0, 30)}`,
                    path: `/Generated Images/Gen: ${job.prompt.slice(0, 30)}`,
                    size: null,
                    content_type: 'image/png',
                    created_at: createdAt,
                    updated_at: createdAt,
                    generation_started_at: job.created_at,
                    generation_completed_at: job.completed_at,
                    prompt: job.prompt,
                    effective_prompt: job.effective_prompt,
                    model: job.model,
                    aspect_ratio: job.aspect_ratio,
                    resolution: job.resolution,
                    actual_width: job.actual_width,
                    actual_height: job.actual_height,
                    actual_aspect_ratio: job.actual_aspect_ratio,
                    style_preset: job.style_preset,
                    source_image_ids: job.source_image_ids,
                } satisfies GeneratedImageGalleryItem;
            })
            .filter(galleryItemMatchesFilters);

        if (completedImages.length) {
            gallery.value = [...completedImages, ...gallery.value];
            galleryTotal.value += completedImages.length;
        }
    };

    const mergeBatchJobs = (batchId: string, jobs: ImageGenerationJob[]) => {
        activeJobs.value = [
            ...activeJobs.value.filter((job) => job.batch_id !== batchId),
            ...jobs.filter((job) => !['completed', 'cancelled'].includes(job.status)),
        ];
    };

    const addActiveBatchId = (batchId: string) => {
        if (!activeBatchIds.value.includes(batchId)) {
            activeBatchIds.value = [...activeBatchIds.value, batchId];
        }
    };

    const removeActiveBatchId = (batchId: string) => {
        activeBatchIds.value = activeBatchIds.value.filter((id) => id !== batchId);
    };

    const syncActiveBatchId = (batchId: string) => {
        const hasVisibleJobs = activeJobs.value.some((job) => job.batch_id === batchId);
        if (hasVisibleJobs) {
            addActiveBatchId(batchId);
        } else {
            removeActiveBatchId(batchId);
        }
    };

    const hasUnfinishedJobs = () =>
        activeJobs.value.some((job) => ['pending', 'processing', 'retrying'].includes(job.status));

    const stopActiveJobsSync = () => {
        if (!activeJobsSyncTimer) return;
        clearInterval(activeJobsSyncTimer);
        activeJobsSyncTimer = null;
    };

    const startActiveJobsSync = () => {
        if (activeJobsSyncTimer || !hasUnfinishedJobs()) return;
        activeJobsSyncTimer = setInterval(() => {
            void syncActiveJobsFromServer(false);
        }, ACTIVE_JOBS_SYNC_INTERVAL_MS);
    };

    const refreshActiveJobsSync = () => {
        if (hasUnfinishedJobs()) {
            startActiveJobsSync();
            return;
        }
        stopActiveJobsSync();
    };

    const sortActiveJobs = () => {
        activeJobs.value = [...activeJobs.value].sort(
            (first, second) =>
                new Date(first.created_at).getTime() - new Date(second.created_at).getTime(),
        );
    };

    const handleJobUpdate = (job: ImageGenerationJob) => {
        if (job.status === 'completed') {
            prependCompletedJobs([job]);
        }

        if (['completed', 'cancelled'].includes(job.status)) {
            activeJobs.value = activeJobs.value.filter((item) => item.id !== job.id);
            syncActiveBatchId(job.batch_id);
            refreshActiveJobsSync();
            return;
        }

        const existingJob = activeJobs.value.find((item) => item.id === job.id);
        activeJobs.value = existingJob
            ? activeJobs.value.map((item) => (item.id === job.id ? job : item))
            : [...activeJobs.value, job];
        sortActiveJobs();
        syncActiveBatchId(job.batch_id);
        refreshActiveJobsSync();
    };

    async function syncActiveJobsFromServer(ensureSocket = true) {
        if (activeJobsSyncInFlight) return;
        activeJobsSyncInFlight = true;
        const previousActiveJobs = activeJobs.value;
        try {
            if (ensureSocket) {
                await connectWebSocket();
            }

            const jobs = await getActiveImageGenerationJobs();
            const serverJobIds = new Set(jobs.map((job) => job.id));
            const staleUnfinishedJobs = previousActiveJobs.filter(
                (job) => ['pending', 'processing', 'retrying'].includes(job.status)
                    && !serverJobIds.has(job.id),
            );

            activeJobs.value = jobs;
            activeBatchIds.value = [
                ...new Set(
                    jobs
                        .filter((job) => ['pending', 'processing', 'retrying'].includes(job.status))
                        .map((job) => job.batch_id),
                ),
            ];

            if (staleUnfinishedJobs.length) {
                await loadGallery();
            }
        } finally {
            activeJobsSyncInFlight = false;
            refreshActiveJobsSync();
        }
    }

    const hydrateActiveJobs = async () => {
        await syncActiveJobsFromServer();
    };

    watch(isWebSocketConnected, (connected) => {
        if (!connected) return;
        void syncActiveJobsFromServer(false);
    });

    const submit = async () => {
        isSubmitting.value = true;
        lastError.value = null;
        try {
            await connectWebSocket();
            const response = await createImageGenerationJobs(buildTasks());
            addPromptHistory();
            addActiveBatchId(response.job_id);
            mergeBatchJobs(response.job_id, response.tasks);
            refreshActiveJobsSync();
        } catch (error) {
            lastError.value = error instanceof Error ? error.message : 'Failed to submit image jobs.';
            throw error;
        } finally {
            isSubmitting.value = false;
        }
    };

    const submitVideo = async (task: VideoGenerationPayload) => {
        isSubmitting.value = true;
        lastError.value = null;
        try {
            await connectWebSocket();
            const response = await createVideoGenerationJobs(task);
            addActiveBatchId(response.job_id);
            mergeBatchJobs(response.job_id, response.tasks);
            refreshActiveJobsSync();
            return response;
        } catch (error) {
            lastError.value = error instanceof Error ? error.message : 'Failed to submit video job.';
            throw error;
        } finally {
            isSubmitting.value = false;
        }
    };

    const addSourceFiles = async (files: File[]) => {
        if (!files.length) return;
        uploadInProgress.value = true;
        try {
            const rootFolder = await getRootFolder();
            let targetFolderId = rootFolder.id;
            const defaultFolder = settingsStore.blockAttachmentSettings.default_upload_folder;

            if (defaultFolder) {
                try {
                    const contents = await getFolderContents(rootFolder.id);
                    const folder = contents.find(
                        (file) => file.name === defaultFolder && file.type === 'folder',
                    );

                    if (folder) {
                        targetFolderId = folder.id;
                    } else {
                        const newFolder = await createFolder(defaultFolder, rootFolder.id);
                        targetFolderId = newFolder.id;
                    }
                } catch (error) {
                    console.warn('Failed to use default upload folder, falling back to root:', error);
                }
            }

            const uploaded = await Promise.all(files.map((file) => uploadFile(file, targetFolderId)));
            sourceImages.value = [...sourceImages.value, ...uploaded];
        } finally {
            uploadInProgress.value = false;
        }
    };

    const isImageFile = (file: FileSystemObject) => {
        if (file.type !== 'file') return false;
        if (file.content_type?.startsWith('image/')) return true;
        return /\.(png|jpe?g|webp|gif|avif)$/i.test(file.name);
    };

    const setSourceImagesFromCloud = (files: FileSystemObject[]) => {
        const seen = new Set<string>();
        sourceImages.value = files.filter((file) => {
            if (!isImageFile(file) || seen.has(file.id)) return false;
            seen.add(file.id);
            return true;
        });
    };

    const removeSourceImage = (fileId: string) => {
        sourceImages.value = sourceImages.value.filter((file) => file.id !== fileId);
    };

    const reorderSourceImages = (fromIndex: number, toIndex: number) => {
        if (fromIndex === toIndex) return;
        const [moved] = sourceImages.value.splice(fromIndex, 1);
        if (!moved) return;
        sourceImages.value.splice(toIndex, 0, moved);
    };

    const setSourceImageReorderActive = (active: boolean) => {
        isReorderingSourceImages.value = active;
    };

    const reuseSettings = (image: GeneratedImageGalleryItem) => {
        prompt.value = image.prompt || image.effective_prompt || '';
        selectedModels.value = image.model ? [image.model] : selectedModels.value;
        aspectRatio.value = image.aspect_ratio || '1:1';
        resolution.value = image.resolution || '1K';
        stylePreset.value = image.style_preset || 'none';
        variationCount.value = 1;
        sourceImages.value = image.source_image_ids.map((id, index) => ({
            id,
            name: `Reference ${index + 1}`,
            path: `/Referenced Images/${id}`,
            type: 'file',
            content_type: 'image/*',
            created_at: image.created_at,
            updated_at: image.updated_at,
            cached: false,
        }));
    };

    const deleteImage = async (imageId: string) => {
        await deleteFileSystemObject(imageId);
        gallery.value = gallery.value.filter((image) => image.id !== imageId);
        galleryTotal.value = Math.max(0, galleryTotal.value - 1);
    };

    const retryFailedJob = async (jobId: string) => {
        await connectWebSocket();
        const job = await retryImageGenerationJob(jobId);
        handleJobUpdate(job);
    };

    const cancelJob = async (jobId: string) => {
        const job = await cancelImageGenerationJob(jobId);
        activeJobs.value = activeJobs.value.filter((item) => item.id !== jobId);
        const hasRemainingBatchJobs = activeJobs.value.some((item) => item.batch_id === job.batch_id);
        if (!hasRemainingBatchJobs) {
            removeActiveBatchId(job.batch_id);
        }
        refreshActiveJobsSync();
    };

    const dismissFailedJob = async (jobId: string) => {
        await dismissImageGenerationJob(jobId);
        activeJobs.value = activeJobs.value.filter((job) => job.id !== jobId);
        refreshActiveJobsSync();
    };

    const clearFailedJobs = async () => {
        await clearFailedImageGenerationJobs();
        activeJobs.value = activeJobs.value.filter((job) => job.status !== 'failed');
        refreshActiveJobsSync();
    };

    return {
        prompt,
        selectedModels,
        aspectRatio,
        resolution,
        stylePreset,
        variationCount,
        sourceImages,
        isReorderingSourceImages,
        sourceImageIds,
        promptHistory,
        gallerySearchQuery,
        galleryModelFilter,
        galleryAspectFilter,
        galleryReferenceFilter,
        activeGalleryFilterCount,
        generationCount,
        exceedsBatchLimit,
        gallery,
        galleryTotal,
        activeJobs,
        activeBatchIds,
        isSubmitting,
        isLoadingGallery,
        isLoadingMoreGallery,
        hasMoreGallery,
        uploadInProgress,
        lastError,
        selectedStyle,
        setDefaultModel,
        toggleModel,
        selectOnlyModel,
        loadPromptHistory,
        applyPromptHistory,
        removePromptHistory,
        clearPromptHistory,
        buildTasks,
        handleJobUpdate,
        clearGalleryFilters,
        hydrateActiveJobs,
        loadGallery,
        loadMoreGallery,
        submit,
        submitVideo,
        addSourceFiles,
        setSourceImagesFromCloud,
        removeSourceImage,
        reorderSourceImages,
        setSourceImageReorderActive,
        reuseSettings,
        deleteImage,
        retryFailedJob,
        cancelJob,
        dismissFailedJob,
        clearFailedJobs,
    };
});
