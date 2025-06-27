<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import type { WheelOption } from '@/types/graph';

import { Position, Handle } from '@vue-flow/core';

// --- Props ---
const props = defineProps<{
    nodeId: string;
    options: WheelOption[];
    type: 'source' | 'target';
    id: string;
    style?: Record<string, string>;
}>();

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();

// --- Local State ---
const isHovering = ref(false);

const compatibleSourceNodeTypes = [NodeTypeEnum.TEXT_TO_TEXT, NodeTypeEnum.PARALLELIZATION];
const compatibleTargetNodeTypes = [NodeTypeEnum.TEXT_TO_TEXT, NodeTypeEnum.PARALLELIZATION];
</script>

<template>
    <div
        class="absolute left-0 z-20 flex h-0 w-full flex-col"
        :class="{
            'top-0': props.type === 'target',
            'bottom-0': props.type === 'source',
        }"
        @mouseenter="isHovering = true"
        @mouseleave="isHovering = false"
    >
        <!-- The Vue Flow Handle -->
        <Handle
            :type="props.type"
            :id="`context_${props.id}`"
            :position="props.type === 'source' ? Position.Bottom : Position.Top"
            style="background: #e5ca5b"
            :style="props.style"
            class="z-30"
            :class="{
                handlebottom: props.type === 'source',
                handletop: props.type === 'target',
            }"
            :connectable="
                (node, connectedEdges) =>
                    handleConnectableInput(node, connectedEdges, 'context', props.type)
            "
        />

        <UiGraphNodeUtilsDragArea
            :nodeId="props.id"
            :type="props.type"
            :compatibleSourceNodeTypes="compatibleSourceNodeTypes"
            :compatibleTargetNodeTypes="compatibleTargetNodeTypes"
            color="golden"
            orientation="horizontal"
        ></UiGraphNodeUtilsDragArea>

        <!-- Radial Menu -->
        <UiGraphNodeUtilsWheel
            v-if="props.type === 'source'"
            :nodeId="props.nodeId"
            :options="props.options"
            :isHovering="isHovering"
            @update:is-hovering="isHovering = $event"
        ></UiGraphNodeUtilsWheel>
    </div>
</template>

<style></style>
