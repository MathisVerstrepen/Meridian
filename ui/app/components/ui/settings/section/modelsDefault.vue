<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();
const { modelsSettings } = storeToRefs(settingsStore);

const defaultChatEntry = SETTINGS_ENTRY.modelsDefaultChat;
const routingEntry = SETTINGS_ENTRY.modelsRouting;
const titleGenerationEntry = SETTINGS_ENTRY.modelsTitleGeneration;
const toolSelectionEntry = SETTINGS_ENTRY.modelsToolSelection;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
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
    </div>
</template>
