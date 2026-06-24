<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { ChromePicker } from 'vue-color';
import 'vue-color/style.css';
import type { CustomThemeColors, ThemeId } from '@/types/settings';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { appearanceSettings } = storeToRefs(settingsStore);

const accentColorEntry = SETTINGS_ENTRY.appearanceAccentColor;
const themeEntry = SETTINGS_ENTRY.appearanceTheme;

const THEME_PALETTES: Record<Exclude<ThemeId, 'custom'>, CustomThemeColors> = {
    light: { softSilk: '#212121', stoneGray: '#757575', anthracite: '#f5f5f5', obsidian: '#ffffff' },
    standard: { softSilk: '#fffcf2', stoneGray: '#ccc5b9', anthracite: '#403d39', obsidian: '#252422' },
    dark: { softSilk: '#ecf2f8', stoneGray: '#c9d1d9', anthracite: '#21262d', obsidian: '#0d1117' },
    oled: { softSilk: '#e5e5e5', stoneGray: '#a9a9a9', anthracite: '#1a1a1a', obsidian: '#000000' },
};

const THEME_LABELS: Record<ThemeId, string> = {
    light: 'Light',
    standard: 'Standard',
    dark: 'GitHub Dark',
    oled: 'OLED',
    custom: 'Custom',
};

const themeCards: { id: ThemeId; colors: CustomThemeColors }[] = [
    { id: 'light', colors: THEME_PALETTES.light },
    { id: 'standard', colors: THEME_PALETTES.standard },
    { id: 'dark', colors: THEME_PALETTES.dark },
    { id: 'oled', colors: THEME_PALETTES.oled },
    {
        id: 'custom',
        colors: appearanceSettings.value.customThemeColors ?? THEME_PALETTES.standard,
    },
];

const getCardColors = (id: ThemeId): CustomThemeColors => {
    if (id === 'custom') return appearanceSettings.value.customThemeColors;
    return THEME_PALETTES[id];
};

const changeTheme = (theme: ThemeId) => {
    appearanceSettings.value.theme = theme;
    if (theme === 'custom') {
        customEditorOpen.value = true;
    } else {
        customEditorOpen.value = false;
    }
};

// --- Accent Color Picker ---
const accentPickerOpen = ref(false);

const resetAccentColor = () => {
    appearanceSettings.value.accentColor = '#eb5e28';
};

// --- Custom Theme Editor ---
const customEditorOpen = ref(appearanceSettings.value.theme === 'custom');

type ColorKey = keyof CustomThemeColors;

const CUSTOM_COLOR_LABELS: Record<ColorKey, { label: string; description: string }> = {
    obsidian: { label: 'Background', description: 'Main app background' },
    anthracite: { label: 'Surface', description: 'Cards, panels, sidebar' },
    softSilk: { label: 'Primary Text', description: 'Headings, main content' },
    stoneGray: { label: 'Secondary Text', description: 'Muted text, borders' },
};

const customColorKeys: ColorKey[] = ['obsidian', 'anthracite', 'softSilk', 'stoneGray'];
const activeColorPicker = ref<ColorKey | null>(null);

const toggleColorPicker = (key: ColorKey) => {
    activeColorPicker.value = activeColorPicker.value === key ? null : key;
};

const startFromTheme = (sourceId: Exclude<ThemeId, 'custom'>) => {
    appearanceSettings.value.customThemeColors = { ...THEME_PALETTES[sourceId] };
    appearanceSettings.value.theme = 'custom';
    customEditorOpen.value = true;
};

// --- Watchers ---
watch(
    () => appearanceSettings.value.accentColor,
    (newColor) => {
        document.documentElement.style.setProperty('--color-ember-glow', newColor);
    },
    { immediate: true },
);

const closeAllPickers = () => {
    accentPickerOpen.value = false;
    activeColorPicker.value = null;
};

const rootRef = ref<HTMLElement | null>(null);
let closePickerListener: ((event: MouseEvent) => void) | null = null;

onMounted(() => {
    closePickerListener = (event: MouseEvent) => {
        if (!rootRef.value) return;
        if (rootRef.value.contains(event.target as Node)) return;
        closeAllPickers();
    };
    document.addEventListener('click', closePickerListener);
});

onUnmounted(() => {
    if (closePickerListener) {
        document.removeEventListener('click', closePickerListener);
    }
});
</script>

<template>
    <div
        ref="rootRef"
        class="divide-stone-gray/10 flex flex-col divide-y"
    >
        <!-- Setting: Application Theme -->
        <div class="py-6">
            <h3 class="text-soft-silk mb-1 font-semibold">{{ themeEntry.title }}</h3>
            <p class="text-stone-gray/80 mb-5 text-sm">
                {{ themeEntry.description }}
            </p>

            <div class="flex flex-wrap gap-3">
                <UiSettingsSectionThemeCard
                    v-for="card in themeCards"
                    :key="card.id"
                    :theme="card.id"
                    :label="THEME_LABELS[card.id]"
                    :colors="getCardColors(card.id)"
                    :accent-color="appearanceSettings.accentColor"
                    :is-selected="appearanceSettings.theme === card.id"
                    @click="changeTheme(card.id)"
                />
            </div>

            <!-- Custom Theme Editor -->
            <Transition
                enter-active-class="transition duration-200 ease-out"
                enter-from-class="opacity-0"
                enter-to-class="opacity-100"
                leave-active-class="transition duration-200 ease-in"
                leave-from-class="opacity-100"
                leave-to-class="opacity-0"
            >
                <div
                    v-if="customEditorOpen && appearanceSettings.theme === 'custom'"
                    class="border-stone-gray/15 bg-anthracite/20 mt-5 rounded-xl border"
                >
                    <div class="flex items-center justify-between px-5 pt-4">
                        <h4 class="text-soft-silk text-sm font-bold">Custom Theme Editor</h4>
                        <div class="flex items-center gap-2">
                            <span class="text-stone-gray/50 text-xs">Start from:</span>
                            <button
                                v-for="sourceId in (['light', 'standard', 'dark', 'oled'] as const)"
                                :key="sourceId"
                                class="text-stone-gray/60 hover:text-ember-glow hover:bg-stone-gray/10 rounded-md px-2 py-1 text-xs font-medium capitalize transition-colors duration-200"
                                @click="startFromTheme(sourceId)"
                            >
                                {{ THEME_LABELS[sourceId] }}
                            </button>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4 px-5 py-4 lg:grid-cols-4">
                        <div
                            v-for="key in customColorKeys"
                            :key="key"
                            class="flex flex-col gap-2"
                        >
                            <div class="flex items-center gap-2">
                                <span class="text-soft-silk text-xs font-semibold">
                                    {{ CUSTOM_COLOR_LABELS[key].label }}
                                </span>
                            </div>
                            <p class="text-stone-gray/50 text-[0.7rem]">
                                {{ CUSTOM_COLOR_LABELS[key].description }}
                            </p>
                            <div class="relative">
                                <button
                                    :class="[
                                        'border-stone-gray/20 hover:border-stone-gray/40 flex h-10 w-full',
                                        'cursor-pointer items-center gap-2 rounded-lg border px-2 transition-colors',
                                        activeColorPicker === key
                                            ? 'border-ember-glow/60 ring-1 ring-ember-glow/30'
                                            : '',
                                    ]"
                                    @click="toggleColorPicker(key)"
                                >
                                    <span
                                        class="h-6 w-6 shrink-0 rounded-md border border-white/10"
                                        :style="{
                                            backgroundColor:
                                                appearanceSettings.customThemeColors[key],
                                        }"
                                    />
                                    <span
                                        class="text-stone-gray/70 font-mono text-xs uppercase"
                                    >
                                        {{ appearanceSettings.customThemeColors[key] }}
                                    </span>
                                </button>
                                <div
                                    v-if="activeColorPicker === key"
                                    class="absolute top-12 left-0 z-20"
                                >
                                    <ChromePicker
                                        v-model="appearanceSettings.customThemeColors[key]"
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- Setting: Accent Color -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ accentColorEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ accentColorEntry.description }}
                </p>
            </div>
            <div class="relative ml-6 shrink-0">
                <div
                    class="relative h-8 w-16 cursor-pointer rounded-lg border-2 border-white/20"
                    :style="{ backgroundColor: appearanceSettings.accentColor }"
                    @click="accentPickerOpen = !accentPickerOpen"
                >
                    <button
                        class="bg-anthracite/50 hover:bg-anthracite/80 absolute top-0 left-0 flex
                            h-fit w-fit items-center justify-center rounded-lg transition-colors"
                        @click.stop="resetAccentColor"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="text-soft-silk h-3 w-3" />
                    </button>
                </div>
                <ChromePicker
                    v-if="accentPickerOpen"
                    v-model="appearanceSettings.accentColor"
                    class="absolute top-10 right-0 z-20"
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
