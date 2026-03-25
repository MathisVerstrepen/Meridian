<script setup lang="ts">
import type { ToolCallArtifact } from '@/types/toolCall';
import SandboxArtifactImageTile from '~/components/ui/chat/utils/sandboxArtifactImageTile.vue';
import GeneratedImageLightbox from '~/components/ui/chat/utils/generatedImageLightbox.vue';

const props = withDefaults(
    defineProps<{
        artifacts: ToolCallArtifact[];
        isStreaming?: boolean;
    }>(),
    {
        isStreaming: false,
    },
);

const imageArtifacts = computed(() => {
    return props.artifacts.filter((artifact) => artifact.kind === 'image');
});

const fileArtifacts = computed(() => {
    return props.artifacts.filter((artifact) => artifact.kind !== 'image');
});

const artifactCountLabel = computed(() => {
    const count = props.artifacts.length;
    return `${count} artifact${count === 1 ? '' : 's'}`;
});

const selectedImageIndex = ref<number | null>(null);

const lightboxImage = computed<{ src: string; prompt: string } | null>(() => {
    const index = selectedImageIndex.value;
    if (index === null) {
        return null;
    }

    const artifact = imageArtifacts.value[index];
    if (!artifact) {
        return null;
    }

    return {
        src: `/api/files/view/${artifact.id}`,
        prompt: artifact.relative_path || artifact.name,
    };
});

const canGoPrevious = computed(() => {
    return selectedImageIndex.value !== null && selectedImageIndex.value > 0;
});

const canGoNext = computed(() => {
    return (
        selectedImageIndex.value !== null &&
        selectedImageIndex.value < imageArtifacts.value.length - 1
    );
});

const handleOpenLightbox = (index: number) => {
    selectedImageIndex.value = index;
};

const openPreviousImage = () => {
    if (!canGoPrevious.value || selectedImageIndex.value === null) {
        return;
    }

    selectedImageIndex.value -= 1;
};

const openNextImage = () => {
    if (!canGoNext.value || selectedImageIndex.value === null) {
        return;
    }

    selectedImageIndex.value += 1;
};

const closeLightbox = () => {
    selectedImageIndex.value = null;
};

watch(imageArtifacts, (artifacts) => {
    if (selectedImageIndex.value === null) {
        return;
    }

    if (selectedImageIndex.value >= artifacts.length) {
        selectedImageIndex.value = artifacts.length ? artifacts.length - 1 : null;
    }
});
</script>

<template>
    <div class="border-stone-gray/15 bg-obsidian/35 mt-4 space-y-4 rounded-2xl border p-4">
        <div class="flex items-center justify-between gap-4">
            <p class="text-soft-silk text-xs font-semibold tracking-wide uppercase">
                Sandbox output{{ props.artifacts.length ? `s` : '' }}
            </p>
            <span class="text-stone-gray text-[11px]">
                {{ artifactCountLabel }}
            </span>
        </div>

        <div v-if="imageArtifacts.length" class="space-y-2">
            <p class="text-stone-gray text-xs font-semibold tracking-wide uppercase">Images</p>
            <div class="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                <SandboxArtifactImageTile
                    v-for="(artifact, index) in imageArtifacts"
                    :key="artifact.id"
                    :artifact="artifact"
                    @open-lightbox="handleOpenLightbox(index)"
                />
            </div>
        </div>

        <div v-if="fileArtifacts.length" class="space-y-2">
            <p class="text-stone-gray text-xs font-semibold tracking-wide uppercase">Files</p>
            <div class="flex flex-wrap gap-2">
                <UiChatUtilsSandboxArtifactDownload
                    v-for="artifact in fileArtifacts"
                    :key="artifact.id"
                    :file-id="artifact.id"
                    :filename="artifact.name"
                    :label="artifact.relative_path || artifact.name"
                    compact
                />
            </div>
        </div>
    </div>

    <GeneratedImageLightbox
        :lightbox-image="lightboxImage"
        :can-go-previous="canGoPrevious"
        :can-go-next="canGoNext"
        @close-lightbox="closeLightbox"
        @previous-image="openPreviousImage"
        @next-image="openNextImage"
    />
</template>
