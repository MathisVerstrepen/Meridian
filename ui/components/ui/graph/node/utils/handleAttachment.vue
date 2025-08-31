<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import { Position, Handle } from '@vue-flow/core';

// --- Props ---
const props = defineProps<{
    type: 'source' | 'target';
    id: string;
    style?: Record<string, string>;
    isDragging: boolean;
}>();

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();

const compatibleSourceNodeTypes = [
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
];
const compatibleTargetNodeTypes = [NodeTypeEnum.FILE_PROMPT, NodeTypeEnum.GITHUB];

// --- Lifecycle Hooks ---
</script>

<template>
    <div
        class="absolute top-0 z-20 flex h-full w-0 flex-col"
        :class="{
            'left-0': props.type === 'target',
            'right-0': props.type === 'source',
        }"
    >
        <Handle
            :id="`attachment_${props.id}`"
            :type="props.type"
            :position="props.type === 'source' ? Position.Right : Position.Left"
            style="background: var(--color-node-cat-attachment)"
            :style="props.style"
            class="z-30"
            :class="{
                handleright: props.type === 'source',
                handleleft: props.type === 'target',
            }"
            :connectable="
                (node, connectedEdges) =>
                    handleConnectableInput(node, connectedEdges, 'attachment', props.type)
            "
        />

        <UiGraphNodeUtilsDragArea
            :node-id="props.id"
            :type="props.type"
            :compatible-source-node-types="compatibleSourceNodeTypes"
            :compatible-target-node-types="compatibleTargetNodeTypes"
            color="heather"
            orientation="vertical"
            :self-node-dragging="props.isDragging"
            :handle-id="`attachment_${props.id}`"
        />
    </div>
</template>

<style scoped></style>
