<script lang="ts" setup>
const props = withDefaults(
    defineProps<{
        lightboxImage: { src: string; prompt: string } | null;
        canGoPrevious?: boolean;
        canGoNext?: boolean;
    }>(),
    {
        canGoPrevious: false,
        canGoNext: false,
    },
);

const emit = defineEmits(['closeLightbox', 'previousImage', 'nextImage']);

const dimensions = ref<string | null>(null);
const hasNavigation = computed(() => props.canGoPrevious || props.canGoNext);

const downloadFilename = computed(() => {
    const timestamp = new Date().getTime();
    return `generated-image-${timestamp}.png`;
});

const onImageLoad = (event: Event) => {
    const img = event.target as HTMLImageElement;
    dimensions.value = `${img.naturalWidth}x${img.naturalHeight}`;
};

watch(
    () => props.lightboxImage,
    () => {
        dimensions.value = null;
    },
);

const handleKeydown = (event: KeyboardEvent) => {
    if (!props.lightboxImage) {
        return;
    }

    if (event.key === 'Escape') {
        emit('closeLightbox');
        return;
    }

    if (event.key === 'ArrowLeft' && props.canGoPrevious) {
        event.preventDefault();
        emit('previousImage');
        return;
    }

    if (event.key === 'ArrowRight' && props.canGoNext) {
        event.preventDefault();
        emit('nextImage');
    }
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
    <Teleport to="body">
        <Transition name="lightbox">
            <div
                v-if="lightboxImage"
                class="lightbox-overlay fixed inset-0 z-[9999] flex items-center justify-center
                    bg-black/95 p-6 backdrop-blur-xl"
                @click.self="emit('closeLightbox')"
            >
                <div class="relative flex max-h-[90vh] max-w-[90vw] flex-col items-center">
                    <button
                        class="absolute -top-12 right-0 flex size-10 cursor-pointer items-center
                            justify-center rounded-full bg-white/10 text-white transition-all
                            duration-200 ease-in-out hover:scale-110 hover:bg-white/20"
                        @click="emit('closeLightbox')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-6 w-6" />
                    </button>

                    <button
                        v-if="hasNavigation"
                        type="button"
                        class="absolute top-1/2 -left-20 hidden -translate-y-1/2 items-center
                            justify-center rounded-full border border-white/10 bg-white/10 p-3
                            text-white transition-all duration-200 ease-in-out md:flex"
                        :class="
                            props.canGoPrevious
                                ? 'cursor-pointer hover:scale-110 hover:bg-white/20'
                                : 'cursor-not-allowed opacity-40'
                        "
                        :disabled="!props.canGoPrevious"
                        @click="emit('previousImage')"
                    >
                        <UiIcon name="FlowbiteChevronDownOutline" class="h-8 w-8 rotate-90" />
                    </button>

                    <button
                        v-if="hasNavigation"
                        type="button"
                        class="absolute top-1/2 -right-20 hidden -translate-y-1/2 items-center
                            justify-center rounded-full border border-white/10 bg-white/10 p-3
                            text-white transition-all duration-200 ease-in-out md:flex"
                        :class="
                            props.canGoNext
                                ? 'cursor-pointer hover:scale-110 hover:bg-white/20'
                                : 'cursor-not-allowed opacity-40'
                        "
                        :disabled="!props.canGoNext"
                        @click="emit('nextImage')"
                    >
                        <UiIcon name="FlowbiteChevronDownOutline" class="h-8 w-8 -rotate-90" />
                    </button>

                    <img
                        :src="lightboxImage.src"
                        :alt="lightboxImage.prompt"
                        class="lightbox-image max-h-[calc(90vh-100px)] max-w-full rounded-xl
                            shadow-2xl shadow-black/50"
                        @load="onImageLoad"
                    />

                    <div class="mt-4 flex max-w-xl flex-col items-center gap-1 text-center text-sm">
                        <div class="flex items-center justify-center gap-2 text-white/70">
                            <UiIcon name="MaterialSymbolsImageRounded" class="h-4 w-4" />
                            <span>{{ lightboxImage.prompt }}</span>
                        </div>
                        <div v-if="dimensions" class="text-xs font-medium text-white/40">
                            {{ dimensions }}
                        </div>
                        <div v-if="hasNavigation" class="text-xs font-medium text-white/40">
                            Use left/right arrow keys to navigate
                        </div>
                    </div>

                    <a
                        :href="lightboxImage.src"
                        :download="downloadFilename"
                        class="bg-soft-silk/10 text-soft-silk hover:bg-soft-silk/20 mt-4 flex
                            items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium
                            no-underline transition-all duration-200 ease-in-out
                            hover:-translate-y-0.5"
                    >
                        <UiIcon name="UilDownloadAlt" class="h-5 w-5" />
                        Download
                    </a>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
.lightbox-overlay {
    --card-accent: rgba(var(--color-ember-glow, 251, 146, 60), 1);
    --loader-accent-soft: rgba(var(--color-ember-glow, 251, 146, 60), 0.15);
}
.lightbox-enter-active,
.lightbox-leave-active {
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.lightbox-enter-from,
.lightbox-leave-to {
    opacity: 0;
}
.lightbox-enter-from .lightbox-image,
.lightbox-leave-to .lightbox-image {
    transform: scale(0.9);
}
</style>
