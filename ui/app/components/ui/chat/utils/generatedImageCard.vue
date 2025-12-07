<script setup lang="ts">
const emit = defineEmits(['openLightbox']);

const props = defineProps<{
    prompt: string;
    imageUrl: string;
}>();

const blobUrl = ref<string | null>(null);
const isLoading = ref(true);
const hasError = ref(false);
const dimensions = ref<string | null>(null);

const fetchAndCreateBlobUrl = async (url: string) => {
    if (!url) return;
    isLoading.value = true;
    hasError.value = false;

    if (blobUrl.value) {
        URL.revokeObjectURL(blobUrl.value);
        blobUrl.value = null;
    }

    try {
        const { data, error } = await useFetch(url, { responseType: 'blob' });

        if (error.value) {
            throw error.value;
        }

        if (data.value) {
            blobUrl.value = URL.createObjectURL(data.value as Blob);
        } else {
            throw new Error('No data received for image');
        }
    } catch (err) {
        console.error('Failed to fetch and display image:', err);
        hasError.value = true;
    } finally {
        isLoading.value = false;
    }
};

const onImageLoad = (event: Event) => {
    const img = event.target as HTMLImageElement;
    dimensions.value = `${img.naturalWidth}x${img.naturalHeight}`;
};

const openLightbox = () => {
    if (blobUrl.value) {
        emit('openLightbox', { src: blobUrl.value, prompt: props.prompt });
    }
};

onMounted(() => {
    fetchAndCreateBlobUrl(props.imageUrl);
});

watch(
    () => props.imageUrl,
    (newUrl) => {
        dimensions.value = null;
        fetchAndCreateBlobUrl(newUrl);
    },
);

onBeforeUnmount(() => {
    if (blobUrl.value) {
        URL.revokeObjectURL(blobUrl.value);
    }
});
</script>

<template>
    <figure
        class="group bg-obsidian border-soft-silk/10 max-w-x my-4 overflow-hidden rounded-xl border"
    >
        <div
            class="relative min-h-[12rem] overflow-hidden"
            :class="{ 'cursor-pointer': !isLoading && !hasError }"
            @click="!isLoading && !hasError && openLightbox()"
        >
            <!-- Loading State -->
            <div
                v-if="isLoading"
                class="bg-obsidian absolute inset-0 flex items-center justify-center"
            >
                <div
                    class="border-soft-silk/50 h-8 w-8 animate-spin rounded-full border-4
                        border-t-transparent"
                ></div>
            </div>

            <!-- Error State -->
            <div
                v-else-if="hasError"
                class="bg-obsidian/50 absolute inset-0 flex flex-col items-center justify-center p-4
                    text-center text-red-400"
            >
                <UiIcon name="MaterialSymbolsErrorOutlineRounded" class="mb-2 h-8 w-8" />
                <p class="text-sm font-medium">Could not load image</p>
                <button
                    class="bg-soft-silk/10 text-soft-silk/80 hover:bg-soft-silk/20 mt-3
                        cursor-pointer rounded-md px-3 py-1.5 text-xs font-semibold
                        transition-colors"
                    @click.stop="fetchAndCreateBlobUrl(imageUrl)"
                >
                    Retry
                </button>
            </div>

            <!-- Image and Controls -->
            <template v-else-if="blobUrl">
                <img
                    :src="blobUrl"
                    :alt="prompt"
                    class="not-prose h-auto w-full"
                    @load="onImageLoad"
                />

                <!-- Dimensions Badge -->
                <div
                    v-if="dimensions"
                    class="absolute bottom-2 left-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[10px]
                        font-medium text-white/90 opacity-0 backdrop-blur-sm transition-opacity
                        duration-200 group-hover:opacity-100"
                >
                    {{ dimensions }}
                </div>

                <div
                    class="absolute top-0 right-0 flex gap-2 p-3 opacity-0 transition-opacity
                        duration-200 ease-in-out group-hover:opacity-100"
                >
                    <button
                        class="border-soft-silk/10 text-soft-silk flex size-9 cursor-pointer
                            items-center justify-center rounded-lg border bg-black/70
                            backdrop-blur-md transition-all duration-200 ease-in-out hover:scale-105
                            hover:bg-black/90"
                        title="View full size"
                        @click.stop="openLightbox"
                    >
                        <UiIcon name="MaterialSymbolsExpandContentRounded" class="h-5 w-5" />
                    </button>
                    <a
                        :href="blobUrl"
                        :download="prompt.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 50) + '.png'"
                        class="border-soft-silk/10 text-soft-silk flex size-9 cursor-pointer
                            items-center justify-center rounded-lg border bg-black/70
                            backdrop-blur-md transition-all duration-200 ease-in-out hover:scale-105
                            hover:bg-black/90"
                        title="Download image"
                        @click.stop
                    >
                        <UiIcon name="UilDownloadAlt" class="h-5 w-5" />
                    </a>
                </div>
            </template>
        </div>
        <figcaption
            class="not-prose text-soft-silk/80 border-soft-silk/10 flex items-center gap-2.5
                border-t px-4 py-3"
        >
            <span class="mt-px flex size-5 shrink-0 items-center justify-center rounded">
                <UiIcon name="IconoirFlash" class="h-4 w-4" />
            </span>
            <span class="flex-1 text-[13px] leading-normal">{{ prompt }}</span>
        </figcaption>
    </figure>
</template>

<style scoped></style>
