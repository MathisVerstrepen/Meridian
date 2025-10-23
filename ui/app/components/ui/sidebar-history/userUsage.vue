<script lang="ts" setup>
// --- Stores ---
const usageStore = useUsageStore();

// --- State from Stores ---
const { linkExtractionUsage, webSearchUsage } = storeToRefs(usageStore);
</script>

<template>
    <div
        class="text-soft-silk bg-obsidian/90 border-stone-gray/10 absolute bottom-0 left-0 z-40 flex
            h-52 w-full flex-col gap-2 rounded-2xl border-2 px-4 pt-4 backdrop-blur-xl"
    >
        <UiSidebarHistoryUserUsageSection title="Web Search Usage" :usage="webSearchUsage" />

        <UiSidebarHistoryUserUsageSection
            title="Link Extraction Usage"
            :usage="linkExtractionUsage"
        />
    </div>
</template>

<style scoped></style>
