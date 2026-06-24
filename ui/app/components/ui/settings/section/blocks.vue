<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { blockSettings } = storeToRefs(globalSettingsStore);
const contextWheelEntry = SETTINGS_ENTRY.blocksContextWheel;
</script>

<template>
    <div class="flex flex-col divide-y divide-stone-gray/10">
        <!-- Setting: Context Wheel -->
        <div class="py-6">
            <div class="max-w-3xl">
                <h3 class="text-soft-silk font-semibold">
                    {{ contextWheelEntry.title }}
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ contextWheelEntry.description }}
                </p>
            </div>
            <div class="mt-4">
                <UiSettingsSectionWheelCreator :slots="blockSettings.contextWheel" />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
