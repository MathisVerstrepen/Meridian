<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();
const { toolsVisualiseSettings } = storeToRefs(settingsStore);
const mermaidOutputEntry = SETTINGS_ENTRY.toolsVisualiseMermaidOutput;
const mermaidRetryEntry = SETTINGS_ENTRY.toolsVisualiseMermaidRetry;
const maxMermaidRetryEntry = SETTINGS_ENTRY.toolsVisualiseMaxMermaidRetry;
const svgOutputEntry = SETTINGS_ENTRY.toolsVisualiseSvgOutput;
const htmlOutputEntry = SETTINGS_ENTRY.toolsVisualiseHtmlOutput;
const mermaidModelEntry = SETTINGS_ENTRY.toolsVisualiseMermaidModel;
const standardModelEntry = SETTINGS_ENTRY.toolsVisualiseStandardModel;
const expertModelEntry = SETTINGS_ENTRY.toolsVisualiseExpertModel;
</script>

<template>
    <div class="flex flex-col">
        <div class="divide-stone-gray/10 flex flex-col divide-y">
            <div class="flex items-center justify-between py-6">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">{{ mermaidOutputEntry.title }}</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        {{ mermaidOutputEntry.description }}
                    </p>
                </div>
                <div class="ml-6 shrink-0">
                    <UiSettingsUtilsSwitch
                        id="visualise-enable-mermaid"
                        :state="toolsVisualiseSettings.enableMermaid"
                        :set-state="
                            (value: boolean) => {
                                toolsVisualiseSettings.enableMermaid = value;
                            }
                        "
                    />
                </div>
            </div>

            <div class="flex items-center justify-between py-6">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">{{ mermaidRetryEntry.title }}</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        {{ mermaidRetryEntry.description }}
                    </p>
                </div>
                <div class="ml-6 shrink-0">
                    <UiSettingsUtilsSwitch
                        id="visualise-enable-mermaid-retry"
                        :state="toolsVisualiseSettings.enableMermaidRetry"
                        :set-state="
                            (value: boolean) => {
                                toolsVisualiseSettings.enableMermaidRetry = value;
                            }
                        "
                    />
                </div>
            </div>

            <div class="flex items-center justify-between py-6">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">{{ maxMermaidRetryEntry.title }}</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        {{ maxMermaidRetryEntry.description }}
                    </p>
                </div>
                <div class="ml-6 shrink-0">
                    <UiSettingsUtilsInputNumber
                        id="visualise-max-mermaid-retry"
                        :number="toolsVisualiseSettings.maxMermaidRetry"
                        :min="0"
                        :max="10"
                        placeholder="Default: 3"
                        class="w-44"
                        @update:number="
                            (value: number) => {
                                toolsVisualiseSettings.maxMermaidRetry = value;
                            }
                        "
                    />
                </div>
            </div>

            <div class="flex items-center justify-between py-6">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">{{ svgOutputEntry.title }}</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        {{ svgOutputEntry.description }}
                    </p>
                </div>
                <div class="ml-6 shrink-0">
                    <UiSettingsUtilsSwitch
                        id="visualise-enable-svg"
                        :state="toolsVisualiseSettings.enableSvg"
                        :set-state="
                            (value: boolean) => {
                                toolsVisualiseSettings.enableSvg = value;
                            }
                        "
                    />
                </div>
            </div>

            <div class="flex items-center justify-between py-6">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">{{ htmlOutputEntry.title }}</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        {{ htmlOutputEntry.description }}
                    </p>
                </div>
                <div class="ml-6 shrink-0">
                    <UiSettingsUtilsSwitch
                        id="visualise-enable-html"
                        :state="toolsVisualiseSettings.enableHtml"
                        :set-state="
                            (value: boolean) => {
                                toolsVisualiseSettings.enableHtml = value;
                            }
                        "
                    />
                </div>
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ mermaidModelEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ mermaidModelEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="visualise-mermaid-default-model"
                    :model="toolsVisualiseSettings.defaultModel"
                    :set-model="
                        (model: string) => {
                            toolsVisualiseSettings.defaultModel = model;
                        }
                    "
                    :disabled="!toolsVisualiseSettings.enableMermaid"
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
                <h3 class="text-soft-silk font-semibold">{{ standardModelEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ standardModelEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="visualise-standard-model"
                    :model="toolsVisualiseSettings.standardModel"
                    :set-model="
                        (model: string) => {
                            toolsVisualiseSettings.standardModel = model;
                        }
                    "
                    :disabled="!toolsVisualiseSettings.enableSvg && !toolsVisualiseSettings.enableHtml"
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
                <h3 class="text-soft-silk font-semibold">{{ expertModelEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ expertModelEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="visualise-expert-model"
                    :model="toolsVisualiseSettings.expertModel"
                    :set-model="
                        (model: string) => {
                            toolsVisualiseSettings.expertModel = model;
                        }
                    "
                    :disabled="!toolsVisualiseSettings.enableSvg && !toolsVisualiseSettings.enableHtml"
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
