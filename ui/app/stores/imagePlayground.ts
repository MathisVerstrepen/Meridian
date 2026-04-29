import { defineStore } from 'pinia';
import type {
    GeneratedImageGalleryItem,
    ImageGenerationJob,
    ImageGenerationTaskPayload,
} from '@/types/imagePlayground';

type StylePreset = {
    label: string;
    suffix: string;
};

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
        uploadFile,
    } = useAPI();
    const { connect: connectWebSocket } = useWebSocket();

    const selectedStyle = computed(() => IMAGE_STYLE_PRESETS[stylePreset.value] ?? IMAGE_STYLE_PRESETS.none);

    const sourceImageIds = computed(() => sourceImages.value.map((image) => image.id));

    const effectivePromptFor = (rawPrompt: string) => {
        const trimmedPrompt = rawPrompt.trim();
        const suffix = selectedStyle.value.suffix.trim();
        return suffix ? `${trimmedPrompt}, ${suffix}` : trimmedPrompt;
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

    const buildTasks = (): ImageGenerationTaskPayload[] => {
        const models = selectedModels.value.filter(Boolean);
        if (!models.length) {
            throw new Error('Select at least one image model.');
        }

        const trimmedPrompt = prompt.value.trim();
        if (!trimmedPrompt) {
            throw new Error('Prompt is required.');
        }

        return models.flatMap((model) =>
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
            const response = await getImagePlaygroundGallery(galleryPageSize, 0);
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
            const response = await getImagePlaygroundGallery(galleryPageSize, galleryOffset.value);
            mergeGalleryPage(response.items, true);
            galleryTotal.value = response.total;
            galleryOffset.value += response.items.length;
            hasMoreGallery.value = galleryOffset.value < response.total;
        } finally {
            isLoadingMoreGallery.value = false;
        }
    };

    const prependCompletedJobs = (jobs: ImageGenerationJob[]) => {
        const visibleGalleryIds = new Set(gallery.value.map((image) => image.id));
        const completedImages = jobs
            .filter((job) => job.status === 'completed' && job.file_id && !visibleGalleryIds.has(job.file_id))
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
                    prompt: job.prompt,
                    effective_prompt: job.effective_prompt,
                    model: job.model,
                    aspect_ratio: job.aspect_ratio,
                    resolution: job.resolution,
                    style_preset: job.style_preset,
                    source_image_ids: job.source_image_ids,
                } satisfies GeneratedImageGalleryItem;
            });

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
            return;
        }

        const existingJob = activeJobs.value.find((item) => item.id === job.id);
        activeJobs.value = existingJob
            ? activeJobs.value.map((item) => (item.id === job.id ? job : item))
            : [...activeJobs.value, job];
        sortActiveJobs();
        syncActiveBatchId(job.batch_id);
    };

    const hydrateActiveJobs = async () => {
        connectWebSocket();
        const jobs = await getActiveImageGenerationJobs();
        activeJobs.value = jobs;
        activeBatchIds.value = [
            ...new Set(
                jobs
                    .filter((job) => ['pending', 'processing', 'retrying'].includes(job.status))
                    .map((job) => job.batch_id),
            ),
        ];
    };

    const submit = async () => {
        isSubmitting.value = true;
        lastError.value = null;
        try {
            connectWebSocket();
            const response = await createImageGenerationJobs(buildTasks());
            addActiveBatchId(response.job_id);
            mergeBatchJobs(response.job_id, response.tasks);
        } catch (error) {
            lastError.value = error instanceof Error ? error.message : 'Failed to submit image jobs.';
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

    const reuseSettings = (image: GeneratedImageGalleryItem) => {
        prompt.value = image.prompt || image.effective_prompt || '';
        selectedModels.value = image.model ? [image.model] : selectedModels.value;
        aspectRatio.value = image.aspect_ratio || '1:1';
        resolution.value = image.resolution || '1K';
        stylePreset.value = image.style_preset || 'none';
        variationCount.value = 1;
    };

    const deleteImage = async (imageId: string) => {
        await deleteFileSystemObject(imageId);
        gallery.value = gallery.value.filter((image) => image.id !== imageId);
        galleryTotal.value = Math.max(0, galleryTotal.value - 1);
    };

    const retryFailedJob = async (jobId: string) => {
        connectWebSocket();
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
    };

    const dismissFailedJob = async (jobId: string) => {
        await dismissImageGenerationJob(jobId);
        activeJobs.value = activeJobs.value.filter((job) => job.id !== jobId);
    };

    const clearFailedJobs = async () => {
        await clearFailedImageGenerationJobs();
        activeJobs.value = activeJobs.value.filter((job) => job.status !== 'failed');
    };

    return {
        prompt,
        selectedModels,
        aspectRatio,
        resolution,
        stylePreset,
        variationCount,
        sourceImages,
        sourceImageIds,
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
        buildTasks,
        handleJobUpdate,
        hydrateActiveJobs,
        loadGallery,
        loadMoreGallery,
        submit,
        addSourceFiles,
        setSourceImagesFromCloud,
        removeSourceImage,
        reuseSettings,
        deleteImage,
        retryFailedJob,
        cancelJob,
        dismissFailedJob,
        clearFailedJobs,
    };
});
