<script lang="ts" setup>
// --- Stores ---
const usageStore = useUsageStore();

// --- Composables ---
const graphEvents = useGraphEvents();

onMounted(() => {
    usageStore.fetchUsage();
});
</script>

<template>
    <div class="relative flex h-full w-full items-center justify-center">
        <slot />

        <UiSidebarHistory
            @mouseenter="graphEvents.emit('enter-history-sidebar', { over: true })"
            @mouseleave="graphEvents.emit('enter-history-sidebar', { over: false })"
        />

        <UiUtilsFullscreenMountpoint />

        <UiGraphNodeUtilsGithubFileSelectMountpoint />

        <UiGraphNodeUtilsFilePromptMountpoint />
    </div>
</template>

<style scoped></style>
