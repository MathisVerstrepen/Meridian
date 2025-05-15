<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useGlobalSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] items-center gap-y-8">
        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Default Model</h3>
            <UiSettingsInfobubble>
                The default model is used when creating a new chat or any bloc using a model.
            </UiSettingsInfobubble>
        </label>
        <UiModelsSelect
            :model="modelsSettings.defaultModel"
            :setModel="
                (model: string) => {
                    modelsSettings.defaultModel = model;
                }
            "
            variant="grey"
            class="h-10 w-[30rem]"
            id="models-default-model"
        ></UiModelsSelect>

        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Exclude Reasoning</h3>
            <UiSettingsInfobubble>
                Exclude reasoning tokens from the model's response. The model will still be able to
                use reasoning internally, but it will not be included in the final response.
            </UiSettingsInfobubble>
        </label>
        <HeadlessSwitch
            v-model="modelsSettings.excludeReasoning"
            :setModel="
                (value: boolean) => {
                    modelsSettings.excludeReasoning = value;
                }
            "
            :class="modelsSettings.excludeReasoning ? 'bg-ember-glow' : 'bg-stone-gray'"
            class="relative inline-flex h-6 w-11 items-center rounded-full"
            role="switch"
            id="models-exclude-reasoning"
        >
            <span class="sr-only">Enable notifications</span>
            <span
                :class="modelsSettings.excludeReasoning ? 'translate-x-6' : 'translate-x-1'"
                class="bg-anthracite inline-block h-4 w-4 transform rounded-full transition"
            ></span>
        </HeadlessSwitch>

        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Global System Prompt</h3>
            <UiSettingsInfobubble>
                The global system prompt is used to set the context for all models. It will be
                prepended to the model's input. This prompt is not saved in the chat history and
                will not be visible in the chat history.
            </UiSettingsInfobubble>
        </label>
        <textarea
            v-model="modelsSettings.globalSystemPrompt"
            :setModel="
                (value: string) => {
                    modelsSettings.globalSystemPrompt = value;
                }
            "
            class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-32 w-[30rem]
                rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
            id="models-global-system-prompt"
        ></textarea>
    </div>
</template>

<style scoped></style>
