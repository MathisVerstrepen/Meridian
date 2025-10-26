<script lang="ts" setup>
import { ReasoningEffortEnum } from '@/types/enums';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Default Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The default model is used when creating a new chat or any block using a model.
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

        <!-- Setting: Exclude Reasoning -->
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

        <!-- Setting: Reasoning Effort -->
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
                <h3 class="text-soft-silk font-semibold">Max Tokens</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The maximum number of tokens to generate in the chat response.
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
                <h3 class="text-soft-silk font-semibold">Temperature</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Controls randomness. Higher values (e.g., 0.8) make output more random, while
                    lower values (e.g., 0.2) make it more deterministic.
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
                <h3 class="text-soft-silk font-semibold">Top P</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Controls nucleus sampling. The model considers tokens with a cumulative
                    probability mass of this value. (e.g., 0.1 means only top 10% likely tokens are
                    considered).
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
                <h3 class="text-soft-silk font-semibold">Top K</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The model samples from the 'k' most likely next tokens at each step. A lower 'k'
                    focuses on higher probability tokens.
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
                <h3 class="text-soft-silk font-semibold">Frequency Penalty</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Penalizes tokens based on their existing frequency, reducing the model's
                    tendency to repeat the same lines.
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
                <h3 class="text-soft-silk font-semibold">Presence Penalty</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Penalizes tokens if they have already appeared in the text, encouraging the
                    model to introduce new topics.
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
                <h3 class="text-soft-silk font-semibold">Repetition Penalty</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Helps prevent the model from repeating itself. It's a penalty applied to tokens
                    that have been generated previously.
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
