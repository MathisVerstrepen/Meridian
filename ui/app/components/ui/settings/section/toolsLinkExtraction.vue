<script lang="ts" setup>
// --- Stores ---
const settingsStore = useSettingsStore();
const usageStore = useUsageStore();

// --- State from Stores ---
const { toolsLinkExtractionSettings } = storeToRefs(settingsStore);
const { linkExtractionUsage, isLoading } = storeToRefs(usageStore);

// --- Methods from Stores ---
const { getUsagePercentage, fetchUsage } = usageStore;

onMounted(() => {
    fetchUsage();
});
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Link Extraction Usage -->
        <div class="py-6">
            <UiSettingsUtilsQueryUsage
                :billing-period-end="linkExtractionUsage.billing_period_end"
                :query-used="linkExtractionUsage.used"
                :query-total="linkExtractionUsage.total"
                :usage-percentage="getUsagePercentage(linkExtractionUsage.used, linkExtractionUsage.total)"
                :is-loading="isLoading"
                query-name="link extraction"
            />
        </div>

        <!-- Setting: Max length of returned content -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Max Content Length</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The maximum length of content (in characters) to return when extracting from a
                    link. Default is 100,000.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="tools-link-extraction-max-length"
                    :number="toolsLinkExtractionSettings.maxLength"
                    :min="1000"
                    placeholder="Default: 100000"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            toolsLinkExtractionSettings.maxLength = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>