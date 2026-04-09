<script lang="ts" setup>
import { ToolEnum } from '@/types/enums';
import type { DataRouting, SidebarNode } from '@/types/graph';

defineProps<{
    node: SidebarNode<DataRouting>;
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
        <div class="flex items-center justify-between rounded-lg py-2">
            <div class="max-w-2xl">
                <h4 class="text-soft-silk text-sm font-semibold">Auto Tool Selection</h4>
            </div>
            <UiSettingsUtilsSwitch
                :id="`${node.id}-auto-tool-selection`"
                :state="node.data.autoSelectTools ?? false"
                :set-state="(value: boolean) => setNodeDataKey('autoSelectTools', value)"
            />
        </div>
        <UiGraphSidebarNodeDataTools
            :node="node"
            :set-node-data-key="setNodeDataKey"
            :disabled="node.data.autoSelectTools ?? false"
            :available-tools="[
                ToolEnum.WEB_SEARCH,
                ToolEnum.LINK_EXTRACTION,
                ToolEnum.IMAGE_GENERATION,
                ToolEnum.EXECUTE_CODE,
                ToolEnum.VISUALISE,
                ToolEnum.ASK_USER,
            ]"
        />
    </div>

    <UiGraphSidebarNodeDataToolSettings :node="node" :set-node-data-key="setNodeDataKey" />
</template>

<style scoped></style>
