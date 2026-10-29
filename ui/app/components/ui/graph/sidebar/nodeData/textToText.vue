<script lang="ts" setup>
import type { DataTextToText, SidebarNode } from '@/types/graph';

defineProps<{
    node: SidebarNode<DataTextToText>;
    setNodeDataKey: (key: string, value: RuntimeValue) => void;
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
            prevent-trigger-on-mount
            :pin-exacto-models="node.data.autoSelectTools || node.data.selectedTools?.length > 0"
            :require-meridian-tools="
                !!node.data.autoSelectTools || !!node.data.selectedTools?.length
            "
            :required-tool-names="node.data.autoSelectTools ? [] : (node.data.selectedTools ?? [])"
        />
    </div>

    <UiGraphSidebarNodeDataToolSelection :node="node" :set-node-data-key="setNodeDataKey" />

    <UiGraphSidebarNodeDataToolSettings :node="node" :set-node-data-key="setNodeDataKey" />
</template>

<style scoped></style>
