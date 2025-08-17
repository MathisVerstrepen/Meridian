<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { blockSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2" for="block-wheel">
            <h3 class="text-stone-gray font-bold">Context Wheel</h3>
            <UiSettingsInfobubble>
                Define the option available in the wheel menu when using "Ctrl+Hover" on a generator
                node handle.
            </UiSettingsInfobubble>
        </label>
        <div id="block-wheel" class="flex items-center gap-2">
            <UiSettingsSectionWheelCreator :slots="blockSettings.contextWheel" />
        </div>
    </div>
</template>

<style scoped></style>
