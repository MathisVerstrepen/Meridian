<script setup lang="ts">
const emit = defineEmits(['openLightbox']);

const props = defineProps<{
    prompt: string;
    imageUrl: string;
}>();

const openLightbox = () => {
    emit('openLightbox', { src: props.imageUrl, prompt: props.prompt });
};
</script>

<template>
    <figure
        class="group bg-obsidian border-soft-silk/10 max-w-x my-4 overflow-hidden rounded-xl border"
    >
        <div class="relative overflow-hidden" @click="openLightbox">
            <img :src="imageUrl" :alt="prompt" class="not-prose h-auto w-full" loading="lazy" />
            <div
                class="absolute top-0 right-0 flex gap-2 p-3 opacity-0 transition-opacity
                    duration-200 ease-in-out group-hover:opacity-100"
            >
                <button
                    class="border-soft-silk/10 text-soft-silk flex size-9 cursor-pointer
                        items-center justify-center rounded-lg border bg-black/70 backdrop-blur-md
                        transition-all duration-200 ease-in-out hover:scale-105 hover:bg-black/90"
                    title="View full size"
                    @click.stop="openLightbox"
                >
                    <UiIcon name="MaterialSymbolsExpandContentRounded" class="h-5 w-5" />
                </button>
                <a
                    :href="imageUrl"
                    download
                    class="border-soft-silk/10 text-soft-silk flex size-9 cursor-pointer
                        items-center justify-center rounded-lg border bg-black/70 backdrop-blur-md
                        transition-all duration-200 ease-in-out hover:scale-105 hover:bg-black/90"
                    title="Download image"
                    @click.stop
                >
                    <UiIcon name="UilDownloadAlt" class="h-5 w-5" />
                </a>
            </div>
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
