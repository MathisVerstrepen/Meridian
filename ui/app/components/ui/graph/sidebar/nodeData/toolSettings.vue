<script lang="ts" setup>
import { ToolEnum } from '@/types/enums';
import type { DataRouting, DataTextToText, SidebarNode } from '@/types/graph';

const props = defineProps<{
    node: SidebarNode<DataTextToText | DataRouting>;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();

const settingsStore = useSettingsStore();
const { toolsImageGenerationSettings, toolsVisualiseSettings } = storeToRefs(settingsStore);

const setVisualiseMode = (mode: 'enableMermaid' | 'enableSvg' | 'enableHtml', value: boolean) => {
    props.setNodeDataKey('visualiseModes', {
        ...(props.node.data.visualiseModes || {}),
        [mode]: value,
    });
};

const hasImageGenerationSettings = computed(
    () =>
        props.node.data.autoSelectTools ||
        props.node.data.selectedTools?.includes(ToolEnum.IMAGE_GENERATION),
);

const hasVisualiseSettings = computed(
    () =>
        props.node.data.autoSelectTools ||
        props.node.data.selectedTools?.includes(ToolEnum.VISUALISE),
);
</script>

<template>
    <div
        v-if="hasImageGenerationSettings"
        class="flex flex-col space-y-2"
    >
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Image Generation Model
        </h3>
        <UiModelsSelect
            :model="node.data.imageModel || toolsImageGenerationSettings.defaultModel"
            :set-model="(model: string) => setNodeDataKey('imageModel', model)"
            :disabled="false"
            to="right"
            from="bottom"
            variant="grey"
            teleport
            prevent-trigger-on-mount
            only-image-models
            hide-tool
        />
    </div>

    <div v-if="hasVisualiseSettings" class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Visualise Output Modes
        </h3>

        <div class="divide-stone-gray/10 flex flex-col divide-y rounded-lg">
            <div class="flex items-center justify-between py-3">
                <div class="max-w-2xl">
                    <h4 class="text-soft-silk text-sm font-semibold">Allow Mermaid</h4>
                    <p class="text-stone-gray/80 mt-1 text-xs">
                        Enable Mermaid generation for this node only.
                    </p>
                </div>
                <UiSettingsUtilsSwitch
                    :id="`${node.id}-visualise-enable-mermaid`"
                    :state="
                        toolsVisualiseSettings.enableMermaid &&
                        (node.data.visualiseModes?.enableMermaid ?? true)
                    "
                    :set-state="(value: boolean) => setVisualiseMode('enableMermaid', value)"
                    :disabled="!toolsVisualiseSettings.enableMermaid"
                />
            </div>

            <div class="flex items-center justify-between py-3">
                <div class="max-w-2xl">
                    <h4 class="text-soft-silk text-sm font-semibold">Allow SVG</h4>
                    <p class="text-stone-gray/80 mt-1 text-xs">
                        Enable SVG visual generation for this node only.
                    </p>
                </div>
                <UiSettingsUtilsSwitch
                    :id="`${node.id}-visualise-enable-svg`"
                    :state="
                        toolsVisualiseSettings.enableSvg &&
                        (node.data.visualiseModes?.enableSvg ?? true)
                    "
                    :set-state="(value: boolean) => setVisualiseMode('enableSvg', value)"
                    :disabled="!toolsVisualiseSettings.enableSvg"
                />
            </div>

            <div class="flex items-center justify-between py-3">
                <div class="max-w-2xl">
                    <h4 class="text-soft-silk text-sm font-semibold">Allow HTML</h4>
                    <p class="text-stone-gray/80 mt-1 text-xs">
                        Enable HTML artifact generation for this node only.
                    </p>
                </div>
                <UiSettingsUtilsSwitch
                    :id="`${node.id}-visualise-enable-html`"
                    :state="
                        toolsVisualiseSettings.enableHtml &&
                        (node.data.visualiseModes?.enableHtml ?? true)
                    "
                    :set-state="(value: boolean) => setVisualiseMode('enableHtml', value)"
                    :disabled="!toolsVisualiseSettings.enableHtml"
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
