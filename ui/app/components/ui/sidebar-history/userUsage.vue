<script lang="ts" setup>
// --- Stores ---
const usageStore = useUsageStore();

// --- State from Stores ---
const { linkExtractionUsage, webSearchUsage } = storeToRefs(usageStore);
</script>

<template>
    <div class="flex h-full w-full flex-col gap-2 px-4 pt-4">
        <UiSidebarHistoryUserUsageSection title="Web Search Usage" :usage="webSearchUsage" />

        <UiSidebarHistoryUserUsageSection
            title="Link Extraction Usage"
            :usage="linkExtractionUsage"
        />
    </div>
</template>

<style scoped></style>