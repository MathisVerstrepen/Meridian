<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();
const { modelsSettings } = storeToRefs(settingsStore);

const maxTokensEntry = SETTINGS_ENTRY.generationMaxTokens;
const temperatureEntry = SETTINGS_ENTRY.generationTemperature;
const topPEntry = SETTINGS_ENTRY.generationTopP;
const topKEntry = SETTINGS_ENTRY.generationTopK;
const frequencyPenaltyEntry = SETTINGS_ENTRY.generationFrequencyPenalty;
const presencePenaltyEntry = SETTINGS_ENTRY.generationPresencePenalty;
const repetitionPenaltyEntry = SETTINGS_ENTRY.generationRepetitionPenalty;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ maxTokensEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ maxTokensEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-max-tokens"
                    :number="modelsSettings.maxTokens"
                    :min="1"
                    placeholder="Minimum: 1"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.maxTokens = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ temperatureEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ temperatureEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-temperature"
                    :number="modelsSettings.temperature"
                    placeholder="Default: 0.7"
                    :min="0"
                    :max="2"
                    :step="0.01"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.temperature = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ topPEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ topPEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-top-p"
                    :number="modelsSettings.topP"
                    placeholder="Default: 1.0"
                    :step="0.01"
                    :min="0"
                    :max="1"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.topP = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ topKEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ topKEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-top-k"
                    :number="modelsSettings.topK"
                    placeholder="Default: 40"
                    :min="0"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.topK = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ frequencyPenaltyEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ frequencyPenaltyEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-frequency-penalty"
                    :number="modelsSettings.frequencyPenalty"
                    placeholder="Default: 0.0"
                    :step="0.01"
                    :min="-2"
                    :max="2"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.frequencyPenalty = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ presencePenaltyEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ presencePenaltyEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-presence-penalty"
                    :number="modelsSettings.presencePenalty"
                    placeholder="Default: 0.0"
                    :step="0.01"
                    :min="-2"
                    :max="2"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.presencePenalty = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ repetitionPenaltyEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ repetitionPenaltyEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="models-repetition-penalty"
                    :number="modelsSettings.repetitionPenalty"
                    placeholder="Default: 1.0"
                    :step="0.01"
                    :min="0"
                    :max="2"
                    class="w-44"
                    @update:number="
                        (value: number) => {
                            modelsSettings.repetitionPenalty = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
