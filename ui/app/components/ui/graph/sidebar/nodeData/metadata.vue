<script lang="ts" setup>
import type { Node } from '@vue-flow/core';
import type { NodeTypeEnum } from '@/types/enums';

defineProps<{
    node: Node;
}>();
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h2 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Metadata
        </h2>
        <div v-if="node.id && node.type" class="flex flex-col gap-1 px-2">
            <p class="text-stone-gray truncate text-xs">ID: {{ node.id }}</p>
            <p class="text-stone-gray flex items-center gap-1 text-xs">
                <span>Type: </span>
                <UiGraphSidebarNodeDataNodeTypeChip
                    :node-type="node.type as NodeTypeEnum"
                ></UiGraphSidebarNodeDataNodeTypeChip>
            </p>
        </div>
    </div>
</template>

<style scoped></style>
