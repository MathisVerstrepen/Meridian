<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { toolsLinkExtractionSettings } = storeToRefs(settingsStore);
const maxContentLengthEntry = SETTINGS_ENTRY.toolsLinkExtraction;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Max length of returned content -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ maxContentLengthEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ maxContentLengthEntry.description }}
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
