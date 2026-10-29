<script setup lang="ts">
import type { DataAgent, SidebarNode } from '@/types/graph';
defineProps<{
    node: SidebarNode<DataAgent>;
    setNodeDataKey: (key: string, value: RuntimeValue) => void;
}>();
</script>
<template>
    <div class="text-soft-silk flex flex-col gap-6">
        <UiLibraryAgentSelection
            :model="node.data.model"
            :selected-tools="node.data.selectedTools ?? []"
            :auto-select-tools="node.data.autoSelectTools"
            :team-id="node.data.teamId"
            @model="setNodeDataKey('model', $event)"
            @team="setNodeDataKey('teamId', $event)"
        />
        <UiGraphSidebarNodeDataToolSelection :node="node" :set-node-data-key="setNodeDataKey" />
        <UiGraphSidebarNodeDataToolSettings :node="node" :set-node-data-key="setNodeDataKey" />
    </div>
</template>
