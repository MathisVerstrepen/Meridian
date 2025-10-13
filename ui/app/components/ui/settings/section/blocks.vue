<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { blockSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="flex flex-col divide-y divide-stone-gray/10">
        <!-- Setting: Context Wheel -->
        <div class="py-6">
            <div class="max-w-3xl">
                <h3 class="text-soft-silk font-semibold">
                    Context Wheel
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Define the options available in the wheel menu when using "Ctrl+Hover" on a
                    generator node handle. Click a slot to configure its main block and quick
                    options.
                </p>
            </div>
            <div class="mt-4">
                <UiSettingsSectionWheelCreator :slots="blockSettings.contextWheel" />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
