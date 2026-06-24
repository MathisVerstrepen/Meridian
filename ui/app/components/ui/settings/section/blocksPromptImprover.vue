<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();

const { blockPromptSettings } = storeToRefs(settingsStore);
const overrideEntry = SETTINGS_ENTRY.blocksPromptImproverOverride;
const modelEntry = SETTINGS_ENTRY.blocksPromptImproverModel;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ overrideEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ overrideEntry.description }}
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
                <h3 class="text-soft-silk font-semibold">{{ modelEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ modelEntry.description }}
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
                    require-structured-outputs
                    hide-tool
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
