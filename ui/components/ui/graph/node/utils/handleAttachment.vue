<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import { Position, Handle } from '@vue-flow/core';

// --- Props ---
const props = defineProps<{
    type: 'source' | 'target';
    id: string;
    style?: Record<string, string>;
}>();

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();

const compatibleSourceNodeTypes = [NodeTypeEnum.TEXT_TO_TEXT, NodeTypeEnum.PARALLELIZATION, NodeTypeEnum.ROUTING];
const compatibleTargetNodeTypes = [NodeTypeEnum.FILE_PROMPT];

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
            :type="props.type"
            :id="`attachment_${props.id}`"
            :position="props.type === 'source' ? Position.Right : Position.Left"
            style="background: #bfaad0"
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
            :nodeId="props.id"
            :type="props.type"
            :compatibleSourceNodeTypes="compatibleSourceNodeTypes"
            :compatibleTargetNodeTypes="compatibleTargetNodeTypes"
            color="heather"
            orientation="vertical"
        ></UiGraphNodeUtilsDragArea>
    </div>
</template>

<style scoped></style>
