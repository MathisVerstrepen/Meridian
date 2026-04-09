<script setup lang="ts">
import type { ToolCallArtifact } from '@/types/toolCall';

const emit = defineEmits<{
    openLightbox: [{ src: string; prompt: string }];
}>();

const props = defineProps<{
    artifact: ToolCallArtifact;
}>();

const { getFileBlob } = useAPI();
const { error } = useToast();

const hasError = ref(false);
const dimensions = ref<string | null>(null);
const isDownloading = ref(false);

const viewUrl = computed(() => `/api/files/view/${props.artifact.id}`);

const displayLabel = computed(() => {
    return props.artifact.relative_path || props.artifact.name;
});

const handleLoad = (event: Event) => {
    const image = event.target as HTMLImageElement;
    dimensions.value = `${image.naturalWidth}x${image.naturalHeight}`;
    hasError.value = false;
};

const handleError = () => {
    hasError.value = true;
    dimensions.value = null;
};

const triggerDownload = async () => {
    if (isDownloading.value) {
        return;
    }

    isDownloading.value = true;

    try {
        const blob = await getFileBlob(props.artifact.id);
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = props.artifact.name || 'image';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error(err);
        error('Failed to download image.');
    } finally {
        isDownloading.value = false;
    }
};

const openLightbox = () => {
    if (hasError.value) {
        return;
    }

    emit('openLightbox', {
        src: viewUrl.value,
        prompt: displayLabel.value,
    });
};
</script>

<template>
    <article class="border-stone-gray/15 bg-obsidian/50 overflow-hidden rounded-xl border">
        <div class="bg-obsidian/70 group relative aspect-square overflow-hidden">
            <button
                type="button"
                class="block h-full w-full"
                :class="{ 'cursor-pointer': !hasError }"
                :disabled="hasError"
                @click="openLightbox"
            >
                <img
                    v-if="!hasError"
                    :src="viewUrl"
                    :alt="displayLabel"
                    class="h-full w-full object-cover transition-transform duration-200"
                    loading="lazy"
                    @load="handleLoad"
                    @error="handleError"
                />
                <div
                    v-else
                    class="text-stone-gray flex h-full items-center justify-center p-4 text-center
                        text-xs"
                >
                    <div class="space-y-2">
                        <UiIcon name="PhImageBroken" class="mx-auto h-5 w-5" />
                        <p>Preview unavailable</p>
                    </div>
                </div>
            </button>

            <button
                v-if="!hasError"
                type="button"
                class="border-stone-gray/15 text-soft-silk absolute top-2 right-2 inline-flex h-8
                    w-8 cursor-pointer items-center justify-center rounded-lg border bg-black/65
                    opacity-0 backdrop-blur-sm transition-all duration-200 group-hover:opacity-100
                    hover:bg-black/80"
                :title="isDownloading ? 'Downloading image' : 'Download image'"
                @click.stop="triggerDownload"
            >
                <UiIcon
                    :name="isDownloading ? 'MaterialSymbolsProgressActivity' : 'UilDownloadAlt'"
                    class="h-4 w-4"
                    :class="{ 'animate-spin': isDownloading }"
                />
            </button>

            <div
                v-if="dimensions && !hasError"
                class="text-soft-silk absolute bottom-2 left-2 rounded-md bg-black/65 px-2 py-1
                    text-[10px] font-medium opacity-0 backdrop-blur-sm transition-opacity
                    duration-200 group-hover:opacity-100"
            >
                {{ dimensions }}
            </div>
        </div>

        <div class="border-stone-gray/10 border-t px-3 py-2.5">
            <div class="min-w-0">
                <p class="text-soft-silk truncate text-sm font-medium">
                    {{ displayLabel }}
                </p>
            </div>
        </div>
    </article>
</template>
