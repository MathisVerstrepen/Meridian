<script lang="ts" setup>
import type { Node } from '@vue-flow/core';
import { ToolEnum } from '@/types/enums';

defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Route Template
        </h3>
        <UiGraphNodeUtilsRoutingGroupSelect
            :routing-group-id="node.data.routeGroupId"
            :set-routing-group-id="(id: string) => setNodeDataKey('routeGroupId', id)"
            color="grey"
            class="h-10"
        />
    </div>

    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">Tools</h3>
        <UiGraphSidebarNodeDataTools
            :node="node"
            :set-node-data-key="setNodeDataKey"
            :available-tools="[ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION]"
        />
    </div>
</template>

<style scoped></style>
