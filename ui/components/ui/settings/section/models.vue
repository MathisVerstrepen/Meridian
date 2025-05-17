<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

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
            class="h-10 w-[20rem]"
            id="models-default-model"
        ></UiModelsSelect>

        <label class="flex gap-2" for="models-default-model">
            <h3 class="text-stone-gray font-bold">Exclude Reasoning</h3>
            <UiSettingsInfobubble>
                Exclude reasoning tokens from the model's response. The model will still be able to
                use reasoning internally, but it will not be included in the final response.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            :state="modelsSettings.excludeReasoning"
            :set-state="
                (value: boolean) => {
                    modelsSettings.excludeReasoning = value;
                }
            "
            id="models-exclude-reasoning"
        ></UiSettingsUtilsSwitch>

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
