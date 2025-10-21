<script lang="ts" setup>
// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { toolsLinkExtractionSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
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