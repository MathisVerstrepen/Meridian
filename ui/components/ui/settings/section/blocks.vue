<script lang="ts" setup>
import { AVAILABLE_WHEELS } from '@/constants';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { blockSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2" for="block-wheel">
            <h3 class="text-stone-gray font-bold">Wheel</h3>
            <UiSettingsInfobubble>
                Define the option available in the wheel menu when using "Ctrl+Hover" on a node
                handle.
            </UiSettingsInfobubble>
        </label>
        <div id="block-wheel" class="flex items-center gap-2">
            <ul class="flex flex-col gap-2">
                <li v-for="wheel in AVAILABLE_WHEELS" :key="wheel.value">
                    <UiSettingsUtilsCheckbox
                        :label="wheel.label"
                        :state="blockSettings.wheel.includes(wheel.value)"
                        :setState="
                            (value: boolean) => {
                                blockSettings.wheel = value
                                    ? [...blockSettings.wheel, wheel.value]
                                    : blockSettings.wheel.filter((item) => item !== wheel.value);
                            }
                        "
                    ></UiSettingsUtilsCheckbox>
                </li>
            </ul>
        </div>
    </div>
</template>

<style scoped></style>
