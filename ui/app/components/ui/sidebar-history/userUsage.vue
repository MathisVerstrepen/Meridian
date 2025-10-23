<script lang="ts" setup>
// --- Stores ---
const usageStore = useUsageStore();

// --- State from Stores ---
const { linkExtractionUsage, webSearchUsage } = storeToRefs(usageStore);
</script>

<template>
    <div class="flex h-full w-full flex-col p-4">
        <div class="mb-3">
            <h3 class="text-soft-silk font-bold tracking-tight">Usage Overview</h3>
            <p class="text-stone-gray/80 text-xs">Your monthly usage summary.</p>
        </div>

        <div class="mb-4 flex flex-col gap-4">
            <UiSidebarHistoryUserUsageSection title="Web Searches" :usage="webSearchUsage" />
            <UiSidebarHistoryUserUsageSection
                title="Link Extractions"
                :usage="linkExtractionUsage"
            />
        </div>

        <NuxtLink
            to="/settings?tab=billing"
            class="hover:bg-anthracite/60 bg-anthracite/90 text-soft-silk focus:ring-ember-glow
                focus:ring-offset-obsidian flex w-full items-center justify-center gap-2 rounded-lg
                border-2 border-transparent py-2 text-sm font-semibold transition-colors
                duration-200 focus:ring-2 focus:ring-offset-2 focus:outline-none"
        >
            Manage Subscription
            <UiIcon name="FlowbiteChevronDownOutline" class="h-4 w-4 -rotate-90" />
        </NuxtLink>
    </div>
</template>

<style scoped></style>
