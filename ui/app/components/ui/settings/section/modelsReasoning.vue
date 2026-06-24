<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { ReasoningEffortEnum } from '@/types/enums';

const settingsStore = useSettingsStore();
const { modelsSettings } = storeToRefs(settingsStore);
const excludeReasoningEntry = SETTINGS_ENTRY.reasoningExclude;
const reasoningEffortEntry = SETTINGS_ENTRY.reasoningEffort;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ excludeReasoningEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ excludeReasoningEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
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

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ reasoningEffortEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ reasoningEffortEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsReasoningSlider
                    id="models-reasoning-effort"
                    :current-reasoning-effort="modelsSettings.reasoningEffort || ReasoningEffortEnum.MEDIUM"
                    class="w-80"
                    @update:reasoning-effort="
                        (value: ReasoningEffortEnum) => {
                            modelsSettings.reasoningEffort = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
