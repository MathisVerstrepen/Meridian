<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { ReasoningEffortEnum } from '@/types/enums';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(settingsStore);
const defaultChatEntry = SETTINGS_ENTRY.modelsDefaultChat;
const routingEntry = SETTINGS_ENTRY.modelsRouting;
const titleGenerationEntry = SETTINGS_ENTRY.modelsTitleGeneration;
const toolSelectionEntry = SETTINGS_ENTRY.modelsToolSelection;
const excludeReasoningEntry = SETTINGS_ENTRY.reasoningExclude;
const reasoningEffortEntry = SETTINGS_ENTRY.reasoningEffort;
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
        <!-- Setting: Default Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ defaultChatEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ defaultChatEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="models-default-model"
                    :model="modelsSettings.defaultModel"
                    :set-model="
                        (model: string) => {
                            modelsSettings.defaultModel = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                />
            </div>
        </div>

        <!-- Setting: Default Routing Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ routingEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ routingEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="models-routing-model"
                    :model="modelsSettings.routingModel"
                    :set-model="
                        (model: string) => {
                            modelsSettings.routingModel = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                    require-structured-outputs
                    hide-tool
                />
            </div>
        </div>

        <!-- Setting: Default Title Generation Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ titleGenerationEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ titleGenerationEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="models-title-generation-model"
                    :model="modelsSettings.titleGenerationModel"
                    :set-model="
                        (model: string) => {
                            modelsSettings.titleGenerationModel = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                    hide-tool
                />
            </div>
        </div>

        <!-- Setting: Default Tool Selection Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ toolSelectionEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ toolSelectionEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="models-auto-tool-selection-model"
                    :model="modelsSettings.autoToolSelectionModel"
                    :set-model="
                        (model: string) => {
                            modelsSettings.autoToolSelectionModel = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                    require-structured-outputs
                    hide-tool
                />
            </div>
        </div>

        <!-- Setting: Exclude Reasoning -->
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

        <!-- Setting: Reasoning Effort -->
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
                    :current-reasoning-effort="
                        modelsSettings.reasoningEffort || ReasoningEffortEnum.MEDIUM
                    "
                    class="w-80"
                    @update:reasoning-effort="
                        (value: ReasoningEffortEnum) => {
                            modelsSettings.reasoningEffort = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Max Tokens -->
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

        <!-- Setting: Temperature -->
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

        <!-- Setting: Top P -->
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

        <!-- Setting: Top K -->
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

        <!-- Setting: Frequency Penalty -->
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

        <!-- Setting: Presence Penalty -->
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

        <!-- Setting: Repetition Penalty -->
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

<style scoped></style>
