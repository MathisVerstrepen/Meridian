<script lang="ts" setup>
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import { IMAGE_PLAYGROUND_ASPECT_RATIOS, imagePlaygroundModelIcon } from '@/utils/imagePlayground';

const emit = defineEmits<{
    (e: 'reuse'): void;
}>();

const playgroundStore = useImagePlaygroundStore();
const modelStore = useModelStore();
const { error: showError, success } = useToast();

const {
    activeJobs,
    activeGalleryFilterCount,
    gallery,
    galleryAspectFilter,
    galleryModelFilter,
    galleryReferenceFilter,
    gallerySearchQuery,
    galleryTotal,
    hasMoreGallery,
    isLoadingGallery,
    isLoadingMoreGallery,
} = storeToRefs(playgroundStore);
const {
    cancelJob,
    clearFailedJobs,
    clearGalleryFilters,
    deleteImage,
    dismissFailedJob,
    hydrateActiveJobs,
    loadGallery,
    loadMoreGallery,
    reuseSettings,
    retryFailedJob,
} = playgroundStore;

const galleryScrollRef = ref<HTMLElement | null>(null);
const gallerySentinelRef = ref<HTMLElement | null>(null);
const selectedImage = ref<GeneratedImageGalleryItem | null>(null);
const hasLoadedInitialGallery = ref(false);
let galleryObserver: IntersectionObserver | null = null;
let galleryFilterTimer: ReturnType<typeof setTimeout> | null = null;

const imageModels = computed(() =>
    modelStore.filterCompatibleModels(modelStore.filteredModels, { outputModality: 'image' }),
);
const gridJobs = computed(() =>
    activeJobs.value.filter((job) => job.media_type !== 'video' && job.status !== 'completed'),
);
const failedJobCount = computed(
    () => gridJobs.value.filter((job) => job.status === 'failed').length,
);
const selectedImageIndex = computed(() =>
    selectedImage.value
        ? gallery.value.findIndex((image) => image.id === selectedImage.value?.id)
        : -1,
);
const canSelectPreviousImage = computed(() => selectedImageIndex.value > 0);
const canSelectNextImage = computed(
    () => selectedImageIndex.value >= 0 && selectedImageIndex.value < gallery.value.length - 1,
);

const hasGalleryFilters = computed(() => activeGalleryFilterCount.value > 0);

const modelDisplayName = (modelId?: string | null) => {
    if (!modelId) return 'Unknown engine';
    return imageModels.value.find((model) => model.id === modelId)?.name || modelId;
};

const modelIconName = (modelId?: string | null) => {
    const found = modelId ? imageModels.value.find((model) => model.id === modelId) : undefined;
    return found ? imagePlaygroundModelIcon(found) : 'MaterialSymbolsElectricBoltRounded';
};

const setupGalleryObserver = () => {
    galleryObserver?.disconnect();
    galleryObserver = null;

    if (!gallerySentinelRef.value || typeof IntersectionObserver === 'undefined') return;

    galleryObserver = new IntersectionObserver(
        (entries) => {
            if (!entries[0]?.isIntersecting) return;
            if (!hasMoreGallery.value || isLoadingGallery.value || isLoadingMoreGallery.value)
                return;
            void loadMoreGallery();
        },
        {
            root: galleryScrollRef.value,
            rootMargin: '640px 0px',
            threshold: 0,
        },
    );
    galleryObserver.observe(gallerySentinelRef.value);
};

const handleDelete = async (image: GeneratedImageGalleryItem) => {
    if (!window.confirm(`Delete "${image.name}"? This cannot be undone.`)) return;

    try {
        await deleteImage(image.id);
        if (selectedImage.value?.id === image.id) {
            selectedImage.value = null;
        }
        success('Image archived.', { title: 'Removed' });
    } catch (error) {
        console.error('Image delete failed:', error);
        showError('Could not delete image.', { title: 'Delete failed' });
    }
};

const handleReuse = (image: GeneratedImageGalleryItem) => {
    reuseSettings(image);
    selectedImage.value = null;
    success('Settings restored.', { title: 'Reset to plate' });
    emit('reuse');
};

const selectPreviousImage = () => {
    if (!canSelectPreviousImage.value) return;
    selectedImage.value = gallery.value[selectedImageIndex.value - 1] || null;
};

const selectNextImage = () => {
    if (!canSelectNextImage.value) return;
    selectedImage.value = gallery.value[selectedImageIndex.value + 1] || null;
};

const handleRetryFailedJob = async (jobId: string) => {
    try {
        await retryFailedJob(jobId);
        success('Failed generation queued again.', { title: 'Retrying' });
    } catch (error) {
        console.error('Image job retry failed:', error);
        showError('Could not retry failed generation.', { title: 'Retry failed' });
    }
};

const handleCancelJob = async (jobId: string) => {
    try {
        await cancelJob(jobId);
        success('Generation cancelled.', { title: 'Cancelled' });
    } catch (error) {
        console.error('Image job cancel failed:', error);
        showError('Could not cancel generation.', { title: 'Cancel failed' });
    }
};

const handleDismissFailedJob = async (jobId: string) => {
    try {
        await dismissFailedJob(jobId);
    } catch (error) {
        console.error('Image job dismiss failed:', error);
        showError('Could not remove failed generation.', { title: 'Remove failed' });
    }
};

const handleClearFailedJobs = async () => {
    try {
        await clearFailedJobs();
    } catch (error) {
        console.error('Clear failed image jobs failed:', error);
        showError('Could not clear failed generations.', { title: 'Clear failed' });
    }
};

const copyPrompt = async (text?: string | null) => {
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
        success('Prompt copied.', { title: 'Copied' });
    } catch (error) {
        console.error('Clipboard copy failed:', error);
        showError('Clipboard unavailable.', { title: 'Copy failed' });
    }
};

onMounted(() => {
    void loadGallery().finally(() => {
        hasLoadedInitialGallery.value = true;
    });
    void hydrateActiveJobs();
    nextTick(setupGalleryObserver);
});

watch([gallerySearchQuery, galleryModelFilter, galleryAspectFilter, galleryReferenceFilter], () => {
    if (!hasLoadedInitialGallery.value) return;
    if (galleryFilterTimer) clearTimeout(galleryFilterTimer);
    galleryFilterTimer = setTimeout(() => {
        void loadGallery();
    }, 250);
});

onBeforeUnmount(() => {
    galleryObserver?.disconnect();
    if (galleryFilterTimer) clearTimeout(galleryFilterTimer);
});
</script>

<template>
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
                    Gallery
                </h2>
                <span class="text-stone-gray/55 font-mono text-[10px] tracking-widest uppercase">
                    {{ galleryTotal }} {{ galleryTotal === 1 ? 'image' : 'images' }}
                </span>
            </div>
            <div class="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-1.5">
                <div class="relative w-42 sm:w-52">
                    <UiIcon
                        name="MdiMagnify"
                        class="text-stone-gray/50 absolute top-1/2 left-2.5 h-3.5 w-3.5
                            -translate-y-1/2"
                    />
                    <input
                        v-model="gallerySearchQuery"
                        class="border-stone-gray/15 bg-obsidian/55 focus:border-ember-glow/60
                            placeholder:text-stone-gray/45 text-soft-silk h-8 w-full rounded-lg
                            border px-2.5 pl-8 text-[11px] outline-none"
                        placeholder="Search prompts…"
                    />
                </div>
                <div class="relative">
                    <select
                        v-model="galleryModelFilter"
                        class="border-stone-gray/15 bg-obsidian/55 text-soft-silk
                            focus:border-ember-glow/60 h-8 max-w-36 appearance-none rounded-lg
                            border py-0 pr-8 pl-2 text-[11px] outline-none"
                    >
                        <option value="">Models</option>
                        <option v-for="model in imageModels" :key="model.id" :value="model.id">
                            {{ model.name }}
                        </option>
                    </select>
                    <UiIcon
                        name="FlowbiteChevronDownOutline"
                        class="text-stone-gray/55 pointer-events-none absolute top-1/2 right-2 h-4
                            w-4 -translate-y-1/2"
                    />
                </div>
                <div class="relative">
                    <select
                        v-model="galleryAspectFilter"
                        class="border-stone-gray/15 bg-obsidian/55 text-soft-silk
                            focus:border-ember-glow/60 h-8 appearance-none rounded-lg border py-0
                            pr-8 pl-2 text-[11px] outline-none"
                    >
                        <option value="">Ratios</option>
                        <option
                            v-for="ratio in IMAGE_PLAYGROUND_ASPECT_RATIOS"
                            :key="ratio.id"
                            :value="ratio.id"
                        >
                            {{ ratio.id }}
                        </option>
                    </select>
                    <UiIcon
                        name="FlowbiteChevronDownOutline"
                        class="text-stone-gray/55 pointer-events-none absolute top-1/2 right-2 h-4
                            w-4 -translate-y-1/2"
                    />
                </div>
                <div class="relative">
                    <select
                        v-model="galleryReferenceFilter"
                        class="border-stone-gray/15 bg-obsidian/55 text-soft-silk
                            focus:border-ember-glow/60 h-8 appearance-none rounded-lg border py-0
                            pr-8 pl-2 text-[11px] outline-none"
                    >
                        <option value="all">Refs</option>
                        <option value="with">With refs</option>
                        <option value="without">No refs</option>
                    </select>
                    <UiIcon
                        name="FlowbiteChevronDownOutline"
                        class="text-stone-gray/55 pointer-events-none absolute top-1/2 right-2 h-4
                            w-4 -translate-y-1/2"
                    />
                </div>
                <button
                    v-if="hasGalleryFilters"
                    type="button"
                    class="border-stone-gray/15 text-stone-gray flex h-8 items-center gap-1
                        rounded-lg border px-2 font-mono text-[9px] tracking-wider uppercase
                        transition hover:border-red-300/45 hover:text-red-300"
                    @click="clearGalleryFilters"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-3 w-3" />
                    <div class="h-2.5">{{ activeGalleryFilterCount }}</div>
                </button>
                <button
                    type="button"
                    :disabled="isLoadingGallery"
                    class="border-stone-gray/15 bg-obsidian/55 text-soft-silk hover:text-soft-silk
                        hover:border-stone-gray/35 hover:bg-obsidian/75
                        disabled:hover:bg-obsidian/55 inline-flex h-8 w-8 cursor-pointer
                        items-center justify-center rounded-lg border backdrop-blur transition
                        disabled:opacity-40"
                    title="Refresh gallery"
                    @click="loadGallery"
                >
                    <UiIcon
                        name="MaterialSymbolsRefreshRounded"
                        class="h-4 w-4"
                        :class="{ 'animate-spin': isLoadingGallery }"
                    />
                </button>
            </div>
        </div>

        <div ref="galleryScrollRef" class="custom_scroll h-full overflow-y-auto px-5 pt-4 pb-24">
            <UiImagesPlaygroundActiveJobsLane
                :jobs="gridJobs"
                :failed-job-count="failedJobCount"
                :model-display-name="modelDisplayName"
                @retry="handleRetryFailedJob"
                @dismiss="handleDismissFailedJob"
                @cancel="handleCancelJob"
                @clear-failed="handleClearFailedJobs"
            />

            <div
                v-if="(!hasLoadedInitialGallery || isLoadingGallery) && !gallery.length"
                class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4"
            >
                <div
                    v-for="n in 8"
                    :key="n"
                    class="border-stone-gray/10 bg-anthracite/30 atelier-skeleton aspect-square
                        rounded-2xl border"
                />
            </div>

            <div
                v-else-if="!gallery.length && !gridJobs.length"
                class="flex min-h-[60vh] flex-col items-center justify-center text-center"
            >
                <div class="empty-frame relative">
                    <div
                        class="border-stone-gray/15 bg-obsidian/40 flex h-32 w-32 items-center
                            justify-center rounded-3xl border"
                    >
                        <UiIcon
                            name="MaterialSymbolsImageRounded"
                            class="text-stone-gray/35 h-14 w-14"
                        />
                    </div>
                </div>
                <h3 class="font-outfit text-soft-silk mt-7 text-2xl font-bold">
                    {{ hasGalleryFilters ? 'No images match' : 'The gallery is empty' }}
                </h3>
                <p class="text-stone-gray/70 mt-2 max-w-sm text-sm">
                    <template v-if="hasGalleryFilters">
                        Adjust or clear filters to widen the archive.
                    </template>
                    <template v-else>
                        Compose a directive on the left, choose your model, and create your first
                        image.
                    </template>
                </p>
            </div>

            <div
                v-else
                class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"
            >
                <UiImagesPlaygroundGalleryTile
                    v-for="(image, index) in gallery"
                    :key="image.id"
                    :image="image"
                    :index="index"
                    :model-display-name="modelDisplayName"
                    @select="selectedImage = $event"
                    @reuse="handleReuse"
                    @delete="handleDelete"
                />
            </div>

            <div ref="gallerySentinelRef" class="flex justify-center py-6">
                <button
                    v-if="hasMoreGallery"
                    type="button"
                    class="border-stone-gray/15 hover:border-ember-glow/50 text-stone-gray
                        hover:text-soft-silk rounded-full border px-5 py-2 text-xs tracking-widest
                        uppercase transition disabled:cursor-not-allowed disabled:opacity-40"
                    :disabled="isLoadingMoreGallery"
                    @click="loadMoreGallery"
                >
                    {{ isLoadingMoreGallery ? 'Loading…' : 'Load more' }}
                </button>
                <span
                    v-else-if="gallery.length"
                    class="text-stone-gray/40 font-mono text-[10px] tracking-widest uppercase"
                >
                    — End of archive —
                </span>
            </div>
        </div>

        <UiImagesPlaygroundImageDetailModal
            :image="selectedImage"
            :model-display-name="modelDisplayName"
            :model-icon-name="modelIconName"
            :can-go-previous="canSelectPreviousImage"
            :can-go-next="canSelectNextImage"
            :position="selectedImageIndex >= 0 ? selectedImageIndex + 1 : null"
            :total="gallery.length"
            @close="selectedImage = null"
            @copy="copyPrompt"
            @reuse="handleReuse"
            @delete="handleDelete"
            @previous="selectPreviousImage"
            @next="selectNextImage"
        />
    </section>
</template>
