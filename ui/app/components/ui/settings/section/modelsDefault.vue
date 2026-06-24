<script lang="ts" setup>
const settingsStore = useSettingsStore();
const { modelsSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Chat Model</h3>
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

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Routing Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The model used to choose routes for routing nodes.
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
                <h3 class="text-soft-silk font-semibold">Title Generation Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The model used to generate and regenerate canvas titles.
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
                <h3 class="text-soft-silk font-semibold">Tool Selection Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The model used when auto tool selection is enabled.
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
