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
const { handleConnectableInputContext } = useEdgeCompatibility();

// --- Local State ---
const isHovering = ref(false);

const isDraggingOver = ref(false);
const isDragging = ref(false);

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
            :id="`${type}_context_${props.id}`"
            :position="props.type === 'source' ? Position.Bottom : Position.Top"
            style="background: #e5ca5b"
            class="z-10"
            :style="props.style"
            :class="{
                handlebottom: props.type === 'source',
                handletop: props.type === 'target',
            }"
            :connectable="handleConnectableInputContext"
        />

        <div
            class="bg-golden-ochre/10 absolute left-1/2 z-0 h-10 w-[90%] -translate-x-1/2 backdrop-blur-md
                transition-all duration-200 ease-in-out"
            :class="{
                '!bg-golden-ochre/25 h-12 w-[92%]': isDraggingOver,
                'bottom-0 rounded-t-2xl': props.type === 'target',
                'top-0 rounded-b-2xl': props.type === 'source',
            }"
            v-if="isDragging"
            @dragover.prevent="isDraggingOver = true"
            @dragleave.prevent="isDraggingOver = false"
        ></div>

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

<style>
.handlebottom {
    width: 45px !important;
    height: 10px !important;
    border: 0;
    border-radius: 0 0 12px 12px;
    transform: translate(-50%, 100%);
    cursor: crosshair;
}
</style>
