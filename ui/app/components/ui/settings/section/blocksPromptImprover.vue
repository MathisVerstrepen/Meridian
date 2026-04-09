<script lang="ts" setup>
const settingsStore = useSettingsStore();

const { blockPromptSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Override Prompt Improver Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Force Prompt Improver to use a specific model for audit, clarification, and
                    improvement instead of the selected downstream target model.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="blocks-prompt-improver-model-override"
                    :state="blockPromptSettings.overridePromptImproverModel"
                    :set-state="
                        (value: boolean) => {
                            blockPromptSettings.overridePromptImproverModel = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Prompt Improver Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    This model is used only when the override above is enabled.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="blocks-prompt-improver-model"
                    :model="blockPromptSettings.promptImproverModel"
                    :set-model="
                        (model: string) => {
                            blockPromptSettings.promptImproverModel = model;
                        }
                    "
                    :disabled="!blockPromptSettings.overridePromptImproverModel"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                    hide-tool
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
