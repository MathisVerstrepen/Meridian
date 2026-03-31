<script lang="ts" setup>
const settingsStore = useSettingsStore();
const { toolsVisualiseSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="flex flex-col">
        <div class="divide-stone-gray/10 flex flex-col divide-y">
            <div class="flex items-center justify-between py-6">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">Enable Mermaid Output</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        Allow the Visualise tool to generate Mermaid diagrams.
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
                    <h3 class="text-soft-silk font-semibold">Enable Mermaid Retry</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        Retry Mermaid generation with parser feedback when backend validation fails.
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
                    <h3 class="text-soft-silk font-semibold">Max Mermaid Retry</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        Number of repair attempts after the initial Mermaid generation. Default is
                        3.
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
                    <h3 class="text-soft-silk font-semibold">Enable SVG Output</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        Allow the Visualise tool to generate SVG visuals.
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
                    <h3 class="text-soft-silk font-semibold">Enable HTML Output</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        Allow the Visualise tool to generate HTML artifacts and interactive widgets.
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
                <h3 class="text-soft-silk font-semibold">Mermaid Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Used when the Visualise tool is called with `output_mode="mermaid"`.
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
                <h3 class="text-soft-silk font-semibold">Standard Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Used for normal diagrams, charts, and explainers generated by the Visualise
                    tool.
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
                <h3 class="text-soft-silk font-semibold">Expert Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Used when the Visualise tool is called with `difficulty="expert"` for more
                    demanding visual representations.
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
