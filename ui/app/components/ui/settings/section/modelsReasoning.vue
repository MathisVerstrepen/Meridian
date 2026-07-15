<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { ReasoningEffortEnum } from '@/types/enums';

const settingsStore = useSettingsStore();
const { modelsSettings } = storeToRefs(settingsStore);
const excludeReasoningEntry = SETTINGS_ENTRY.reasoningExclude;
const reasoningEffortEntry = SETTINGS_ENTRY.reasoningEffort;
const reasoningTiePreferenceEntry = SETTINGS_ENTRY.reasoningTiePreference;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex flex-col gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ excludeReasoningEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ excludeReasoningEntry.description }}
                </p>
            </div>
            <div class="shrink-0 sm:ml-6">
                <UiSettingsUtilsSwitch
                    id="models-exclude-reasoning"
                    :state="modelsSettings.excludeReasoning"
                    :set-state="
                        (value: boolean) => {
                            modelsSettings.excludeReasoning = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex flex-col gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ reasoningEffortEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ reasoningEffortEntry.description }}
                </p>
            </div>
            <div class="w-full sm:ml-6 sm:w-72 sm:shrink-0">
                <UiSettingsUtilsReasoningSlider
                    id="models-reasoning-effort"
                    :current-reasoning-effort="modelsSettings.reasoningEffort || ReasoningEffortEnum.MEDIUM"
                    @update:reasoning-effort="
                        (value: ReasoningEffortEnum) => {
                            modelsSettings.reasoningEffort = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between gap-6 py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ reasoningTiePreferenceEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ reasoningTiePreferenceEntry.description }}
                </p>
            </div>
            <div class="shrink-0">
                <UiSettingsUtilsSwitch
                    id="models-prefer-higher-reasoning-effort"
                    :state="modelsSettings.preferHigherReasoningEffort"
                    :set-state="
                        (value: boolean) => {
                            modelsSettings.preferHigherReasoningEffort = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
