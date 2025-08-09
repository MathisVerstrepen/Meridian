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
    NodeTypeEnum.PROMPT,
];
const compatibleTargetNodeTypes = [NodeTypeEnum.PROMPT];
</script>

<template>
    <div
        class="absolute left-0 z-20 flex h-0 w-full flex-col"
        :class="{
            'top-0': props.type === 'target',
            'bottom-0': props.type === 'source',
        }"
    >
        <Handle
            :type="props.type"
            :id="`prompt_${props.id}`"
            :position="props.type === 'source' ? Position.Bottom : Position.Top"
            style="background: #b2c7db"
            :style="props.style"
            class="z-30"
            :class="{
                handlebottom: props.type === 'source',
                handletop: props.type === 'target',
            }"
            :connectable="
                (node, connectedEdges) =>
                    handleConnectableInput(node, connectedEdges, 'prompt', props.type)
            "
        />

        <UiGraphNodeUtilsDragArea
            :nodeId="props.id"
            :type="props.type"
            :compatibleSourceNodeTypes="compatibleSourceNodeTypes"
            :compatibleTargetNodeTypes="compatibleTargetNodeTypes"
            color="blue"
            orientation="horizontal"
            :selfNodeDragging="props.isDragging"
            :handleId="`prompt_${props.id}`"
        ></UiGraphNodeUtilsDragArea>
    </div>
</template>

<style scoped></style>
