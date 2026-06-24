<script lang="ts" setup>
import { ReasoningEffortEnum } from '@/types/enums';

const settingsStore = useSettingsStore();
const { modelsSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Exclude Reasoning</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Exclude reasoning tokens from the model's response. The model will still reason
                    internally, but it will not be included in the final response.
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
                <h3 class="text-soft-silk font-semibold">Reasoning Effort</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Controls how much effort the model will put into reasoning before generating a
                    response.
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
