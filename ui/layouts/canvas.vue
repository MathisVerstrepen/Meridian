<script lang="ts" setup>
// --- Composables ---
const graphEvents = useGraphEvents();
</script>

<template>
    <div class="relative flex h-full w-full items-center justify-center">
        <slot />

        <UiSidebarHistory
            @mouseenter="graphEvents.emit('enter-history-sidebar', { over: true })"
            @mouseleave="graphEvents.emit('enter-history-sidebar', { over: false })"
        />

        <UiUtilsFullscreenMountpoint></UiUtilsFullscreenMountpoint>
    </div>
</template>

<style scoped></style>
