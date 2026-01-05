<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import type { WheelSlot } from '@/types/settings';

import { Position, Handle } from '@vue-flow/core';

// --- Props ---
const props = defineProps<{
    nodeId: string;
    options: WheelSlot[];
    type: 'source' | 'target';
    id: string;
    style?: Record<string, string>;
    isDragging: boolean;
    multipleInput?: boolean;
    isVisible?: boolean;
}>();

// --- Stores ---
const dragStore = useDragStore();

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();
const { snappedHandle } = useEdgeSnapping();

// --- Local State ---
const isHovering = ref(false);

const compatibleSourceNodeTypes = [
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
];
const compatibleTargetNodeTypes = [
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
];

// --- Computed ---
const isSnapped = computed(
    () =>
        snappedHandle.value?.handleId === `context_${props.id}` &&
        snappedHandle.value?.type === props.type,
);
</script>

<template>
    <div
        class="absolute left-0 flex h-0 w-full flex-col"
        :class="{
            'top-0': props.type === 'target',
            'bottom-0': props.type === 'source',
        }"
        @mouseenter="isHovering = true"
        @mouseleave="isHovering = false"
    >
        <!-- The Vue Flow Handle -->
        <Handle
            :id="`context_${props.id}`"
            :type="props.type"
            :position="props.type === 'source' ? Position.Bottom : Position.Top"
            style="background: var(--color-node-cat-context)"
            :style="props.style"
            class="z-30 transition-transform duration-200"
            :class="{
                handlebottom: props.type === 'source',
                handletop: props.type === 'target',
                'translate-x-[12.5%] scale-125': isSnapped,
            }"
            :connectable="
                (node, connectedEdges) =>
                    handleConnectableInput(
                        node,
                        connectedEdges,
                        'context',
                        props.type,
                        multipleInput || false,
                    )
            "
        />

        <UiGraphNodeUtilsDragArea
            v-if="props.isVisible && dragStore.isGlobalDragging && !props.isDragging"
            :node-id="props.id"
            :type="props.type"
            :compatible-source-node-types="compatibleSourceNodeTypes"
            :compatible-target-node-types="compatibleTargetNodeTypes"
            color="golden"
            orientation="horizontal"
            :handle-id="`context_${props.id}`"
        />

        <!-- Radial Menu -->
        <UiGraphNodeUtilsWheel
            v-if="props.type === 'source'"
            :node-id="props.nodeId"
            :options="props.options"
            :is-hovering="isHovering"
            @update:is-hovering="isHovering = $event"
        />
    </div>
</template>

<style></style>
