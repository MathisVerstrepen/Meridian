<script lang="ts" setup>
defineProps<{
    lightboxImage: { src: string; prompt: string } | null;
}>();

defineEmits(['closeLightbox']);
</script>

<template>
    <Teleport to="body">
        <Transition name="lightbox">
            <div
                v-if="lightboxImage"
                class="lightbox-overlay fixed inset-0 z-[9999] flex items-center justify-center
                    bg-black/95 p-6 backdrop-blur-xl"
                @click.self="$emit('closeLightbox')"
                @keydown.escape="$emit('closeLightbox')"
            >
                <div class="relative flex max-h-[90vh] max-w-[90vw] flex-col items-center">
                    <button
                        class="absolute -top-12 right-0 flex size-10 cursor-pointer items-center
                            justify-center rounded-full bg-white/10 text-white transition-all
                            duration-200 ease-in-out hover:scale-110 hover:bg-white/20"
                        @click="$emit('closeLightbox')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-6 w-6" />
                    </button>
                    <img
                        :src="lightboxImage.src"
                        :alt="lightboxImage.prompt"
                        class="lightbox-image max-h-[calc(90vh-100px)] max-w-full rounded-xl
                            shadow-2xl shadow-black/50"
                    />
                    <div
                        class="mt-4 flex max-w-xl items-center gap-2 text-center text-sm
                            text-white/70"
                    >
                        <UiIcon name="IconoirFlash" class="h-4 w-4" />
                        <span>{{ lightboxImage.prompt }}</span>
                    </div>
                    <a
                        :href="lightboxImage.src"
                        download
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
