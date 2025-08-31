<script lang="ts" setup>
const props = defineProps<{
    renderedElement: HTMLElement | null;
    rawMermaidElement: string | undefined;
}>();

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Core Logic Functions ---
const openFullscreen = () => {
    if (props.renderedElement) {
        const fullscreenMountpoint = document.getElementById('fullscreen-mountpoint');
        if (fullscreenMountpoint) {
            fullscreenMountpoint.appendChild(props.renderedElement);
            graphEvents.emit('open-fullscreen', { open: true, rawElement: props.rawMermaidElement });
        }
    }
};
</script>

<template>
    <button
        class="flex items-center justify-center rounded-full transition-colors duration-200 ease-in-out
            hover:cursor-pointer"
        aria-label="Enter Fullscreen"
        v-bind="$attrs"
        @click="openFullscreen"
    >
        <UiIcon name="MingcuteFullscreen2Line" class="text-soft-silk/80 h-5 w-5" />
    </button>

    <div class="mounted-element"/>
</template>

<style scoped></style>
