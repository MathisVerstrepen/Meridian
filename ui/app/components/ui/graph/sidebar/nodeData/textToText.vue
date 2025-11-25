<script lang="ts" setup>
import type { Node } from '@vue-flow/core';
import { ToolEnum } from '@/types/enums';

defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
    setCurrentModel: (model: string) => void;
}>();
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">Model</h3>
        <UiModelsSelect
            :model="node.data.model"
            :set-model="
                (model: string) => {
                    setCurrentModel(model);
                    setNodeDataKey('model', model);
                }
            "
            :disabled="false"
            to="right"
            from="bottom"
            variant="grey"
            teleport
            prevent-trigger-on-mount
            :pin-exacto-models="node.data.selectedTools?.length > 0"
        />
    </div>

    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">Tools</h3>
        <UiGraphSidebarNodeDataTools
            :node="node"
            :set-node-data-key="setNodeDataKey"
            :available-tools="[
                ToolEnum.WEB_SEARCH,
                ToolEnum.LINK_EXTRACTION,
                ToolEnum.IMAGE_GENERATION,
            ]"
        />
    </div>

    <!-- Image Generation Model Selector -->
    <div
        v-if="node.data.selectedTools?.includes(ToolEnum.IMAGE_GENERATION)"
        class="flex flex-col space-y-2"
    >
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Image Generation Model
        </h3>
        <UiModelsSelect
            :model="node.data.imageModel || 'openai/gpt-5-image-mini'"
            :set-model="(model: string) => setNodeDataKey('imageModel', model)"
            :disabled="false"
            to="right"
            from="bottom"
            variant="grey"
            teleport
            prevent-trigger-on-mount
            only-image-models
        />
    </div>
</template>

<style scoped></style>
