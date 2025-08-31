<script lang="ts" setup>
import { ReasoningEffortEnum } from '@/types/enums';

// --- Stores ---
const globalSettingsStore = useSettingsStore();
const modelStore = useModelStore();
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsDropdownSettings } = storeToRefs(settingsStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { setModels, sortModels, triggerFilter } = modelStore;

// --- Composables ---
const { refreshOpenRouterModels } = useAPI();
const { success } = useToast();

// --- Core functions ---
const refreshModels = async () => {
    const modelList = await refreshOpenRouterModels();
    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();
    success(`Refreshed OpenRouter models successfully (${modelList.data.length} models)`);
};
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2" for="models-refresh">
            <h3 class="text-stone-gray font-bold">Refresh OpenRouter Models</h3>
            <UiSettingsInfobubble>
                Refresh the list of models from OpenRouter. This will update the list of available
                models in the dropdown.
            </UiSettingsInfobubble>
        </label>
        <div id="models-refresh">
            <button
                class="border-stone-gray/20 bg-anthracite/20 text-stone-gray hover:bg-anthracite focus:border-ember-glow
                    flex h-10 w-fit items-center justify-center gap-2 rounded-lg border-2 px-8 transition-colors
                    duration-200 ease-in-out focus:border-2 focus:outline-none"
                @click="refreshModels"
            >
                <UiIcon name="MaterialSymbolsChangeCircleRounded" class="h-5 w-5" />
                Refresh Models
            </button>
        </div>

        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Default Model</h3>
            <UiSettingsInfobubble>
                The default model is used when creating a new chat or any bloc using a model.
            </UiSettingsInfobubble>
        </label>
        <UiModelsSelect
            id="models-default-model"
            :model="modelsSettings.defaultModel"
            :set-model="
                (model: string) => {
                    modelsSettings.defaultModel = model;
                }
            "
            :disabled="false"
            variant="grey"
            class="h-10 w-[20rem]"
        />

        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Exclude Reasoning</h3>
            <UiSettingsInfobubble>
                Exclude reasoning tokens from the model's response. The model will still be able to
                use reasoning internally, but it will not be included in the final response.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            id="models-exclude-reasoning"
            :state="modelsSettings.excludeReasoning"
            :set-state="
                (value: boolean) => {
                    modelsSettings.excludeReasoning = value;
                }
            "
        />

        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Global System Prompt</h3>
            <UiSettingsInfobubble>
                The global system prompt is used to set the context for all models. It will be
                prepended to the model's input. This prompt is not saved in the chat history and
                will not be visible in the chat history.
            </UiSettingsInfobubble>
        </label>
        <textarea
            id="models-global-system-prompt"
            v-model="modelsSettings.globalSystemPrompt"
            :setModel="
                (value: string) => {
                    modelsSettings.globalSystemPrompt = value;
                }
            "
            class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-32 w-[30rem]
                rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
        />

        <label class="flex gap-2" for="models-generate-mermaid">
            <h3 class="text-stone-gray font-bold">Generate Mermaid Diagrams</h3>
            <UiSettingsInfobubble>
                Enable this option to allow the model to generate Mermaid diagrams in its responses. Mermaid
                is a simple markdown-like script language for generating charts and diagrams.
                When enabled, a new instruction will be added to the system prompt to allow the model
                to generate Mermaid diagrams.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            id="models-generate-mermaid"
            :state="modelsSettings.generateMermaid"
            :set-state="
                (value: boolean) => {
                    modelsSettings.generateMermaid = value;
                }
            "
        />

        <label class="mb-2 flex gap-2" for="models-reasoning-effort">
            <h3 class="text-stone-gray font-bold">Reasoning Effort</h3>
            <UiSettingsInfobubble>
                The reasoning effort to use for the chat response. This value controls how much
                effort the model will put into reasoning before generating a response.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsReasoningSlider
            id="models-reasoning-effort"
            :current-reasoning-effort="modelsSettings.reasoningEffort || ReasoningEffortEnum.MEDIUM"
            class="w-[30rem]"
            @update:reasoning-effort="
                (value: ReasoningEffortEnum) => {
                    modelsSettings.reasoningEffort = value;
                }
            "
        />

        <!-- Max Tokens -->
        <label class="mb-2 flex gap-2" for="models-max-tokens">
            <h3 class="text-stone-gray font-bold">Max Tokens</h3>
            <UiSettingsInfobubble direction="left">
                The maximum number of tokens to generate in the chat response.
            </UiSettingsInfobubble>
        </label>
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

        <!-- Temperature -->
        <label class="mb-2 flex gap-2" for="models-temperature">
            <h3 class="text-stone-gray font-bold">Temperature</h3>
            <UiSettingsInfobubble direction="left">
                The temperature to use for the chat response. Higher values will make the response
                more random, while lower values will make it more deterministic.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsInputNumber
            id="models-temperature"
            :number="modelsSettings.temperature"
            placeholder="Default: 0.7"
            :min="0"
            :max="2"
            class="w-44"
            @update:number="
                (value: number) => {
                    modelsSettings.temperature = value;
                }
            "
        />

        <!-- Top P -->
        <label class="mb-2 flex gap-2" for="models-top-p">
            <h3 class="text-stone-gray font-bold">Top P</h3>
            <UiSettingsInfobubble direction="left">
                The Top P value to use for the chat response. Top P is a filter that controls how
                many different words or phrases the language model considers when it’s trying to
                predict the next word. A lower value means the model will only consider the most
                likely words, while a higher value means it will consider more possibilities.
            </UiSettingsInfobubble>
        </label>
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

        <!-- Top K -->
        <label class="mb-2 flex gap-2" for="models-top-k">
            <h3 class="text-stone-gray font-bold">Top K</h3>
            <UiSettingsInfobubble direction="left">
                The Top K value to use for the chat response. Top K sample from the k most likely
                next tokens at each step. Lower k focuses on higher probability tokens.
            </UiSettingsInfobubble>
        </label>
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

        <!-- Frequency Penalty -->
        <label class="mb-2 flex gap-2" for="models-frequency-penalty">
            <h3 class="text-stone-gray font-bold">Frequency Penalty</h3>
            <UiSettingsInfobubble direction="left">
                The frequency penalty to use for the chat response. This value penalizes new tokens
                based on their existing frequency in the text so far, decreasing the model's
                likelihood to repeat the same line verbatim.
            </UiSettingsInfobubble>
        </label>
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

        <!-- Presence Penalty -->
        <label class="mb-2 flex gap-2" for="models-presence-penalty">
            <h3 class="text-stone-gray font-bold">Presence Penalty</h3>
            <UiSettingsInfobubble direction="left">
                The presence penalty to use for the chat response. This value penalizes new tokens
                based on whether they appear in the text so far, decreasing the model's likelihood
                to repeat the same line verbatim.
            </UiSettingsInfobubble>
        </label>
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

        <!-- Repetition Penalty -->
        <label class="mb-2 flex gap-2" for="models-repetition-penalty">
            <h3 class="text-stone-gray font-bold">Repetition Penalty</h3>
            <UiSettingsInfobubble direction="left">
                The repetition penalty to use for the chat response. This value penalizes new tokens
                based on their existing frequency in the text so far, decreasing the model's
                likelihood to repeat the same line verbatim.
            </UiSettingsInfobubble>
        </label>
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
</template>

<style scoped></style>
