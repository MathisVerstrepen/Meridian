<script lang="ts" setup>
import { ChromePicker } from 'vue-color';
import 'vue-color/style.css';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { appearanceSettings } = storeToRefs(settingsStore);

const changeTheme = (theme: 'light' | 'dark' | 'oled' | 'standard') => {
    appearanceSettings.value.theme = theme;
};

const pickerOpen = ref(false);

// --- Watchers ---
watch(
    () => appearanceSettings.value.accentColor,
    (newColor) => {
        document.documentElement.style.setProperty('--color-ember-glow', newColor);
    },
    { immediate: true },
);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Accent Color -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Accent Color</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose the primary accent color used for buttons, highlights, and other key
                    interface elements.
                </p>
            </div>
            <div class="relative ml-6 shrink-0">
                <div
                    class="relative h-8 w-16 cursor-pointer rounded-lg border-2 border-white/20"
                    :style="{ backgroundColor: appearanceSettings.accentColor }"
                    @click="pickerOpen = !pickerOpen"
                >
                    <button
                        class="bg-anthracite/50 hover:bg-anthracite/80 absolute top-0 left-0 flex h-fit w-fit items-center
                            justify-center rounded-lg transition-colors"
                        @click.stop="
                            () => {
                                appearanceSettings.accentColor = '#eb5e28';
                            }
                        "
                    >
                        <UiIcon name="MaterialSymbolsClose" class="text-soft-silk h-3 w-3" />
                    </button>
                </div>
                <ChromePicker
                    v-if="pickerOpen"
                    v-model="appearanceSettings.accentColor"
                    class="absolute top-10 right-0 z-10"
                    @click.stop
                />
            </div>
        </div>

        <!-- Setting: Application Theme -->
        <div class="flex items-center justify-between py-6">
            <div class="w-full">
                <h3 class="text-soft-silk mb-4 font-semibold">Application Theme</h3>
                <div class="mx-auto flex w-fit gap-4 px-2">
                    <UiSettingsSectionThemeCard theme="light" @click="changeTheme('light')" />
                    <UiSettingsSectionThemeCard theme="dark" @click="changeTheme('dark')" />
                    <UiSettingsSectionThemeCard theme="oled" @click="changeTheme('oled')" />
                    <UiSettingsSectionThemeCard theme="standard" @click="changeTheme('standard')" />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
