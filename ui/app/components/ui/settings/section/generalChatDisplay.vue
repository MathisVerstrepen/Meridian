<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const globalSettingsStore = useSettingsStore();
const { generalSettings } = storeToRefs(globalSettingsStore);

const thinkingPanelsEntry = SETTINGS_ENTRY.chatThinkingPanels;
const thinkingContextEntry = SETTINGS_ENTRY.chatThinkingContext;
const messageCollapsingEntry = SETTINGS_ENTRY.chatMessageCollapsing;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ thinkingPanelsEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ thinkingPanelsEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-always-thinking-disclosures"
                    :state="generalSettings.alwaysThinkingDisclosures"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.alwaysThinkingDisclosures = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ thinkingContextEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ thinkingContextEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-include-thinking-in-context"
                    :state="generalSettings.includeThinkingInContext"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.includeThinkingInContext = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ messageCollapsingEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ messageCollapsingEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-enable-message-collapsing"
                    :state="generalSettings.enableMessageCollapsing"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.enableMessageCollapsing = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
