<script lang="ts" setup>
import { ChromePicker } from 'vue-color';
import 'vue-color/style.css';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { appearanceSettings } = storeToRefs(settingsStore);

const changeTheme = (theme: 'light' | 'dark' | 'oled' | 'standard') => {
    console.log(`Changing theme to: ${theme}`);
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
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2" for="general-open-chat-view-on-new-canvas">
            <h3 class="text-stone-gray font-bold">Accent Color</h3>
        </label>

        <div
            class="relative h-8 w-16 cursor-pointer rounded-lg border-2 border-white/20"
            :style="{ backgroundColor: appearanceSettings.accentColor }"
            @click="pickerOpen = !pickerOpen"
        >
            <div
                class="bg-anthracite/50 absolute top-0 left-0 flex h-fit w-fit items-center justify-center rounded-lg"
                @click.stop="
                    () => {
                        appearanceSettings.accentColor = '#eb5e28';
                    }
                "
            >
                <UiIcon name="MaterialSymbolsClose" class="text-soft-silk h-3 w-3" />
            </div>
            <ChromePicker
                v-if="pickerOpen"
                v-model="appearanceSettings.accentColor"
                class="absolute top-0 left-20 z-10"
                @click.stop
            />
        </div>

        <label class="flex gap-2" for="general-open-chat-view-on-new-canvas">
            <h3 class="text-stone-gray font-bold">Application Theme</h3>
        </label>

        <div class="col-span-2">
            <div class="mx-auto flex w-fit gap-4 px-2">
                <UiSettingsSectionThemeCard theme="light" @click="changeTheme('light')" />
                <UiSettingsSectionThemeCard theme="dark" @click="changeTheme('dark')" />
                <UiSettingsSectionThemeCard theme="oled" @click="changeTheme('oled')" />
                <UiSettingsSectionThemeCard theme="standard" @click="changeTheme('standard')" />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
