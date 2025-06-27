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
const { handleConnectableInputPrompt } = useEdgeCompatibility();

const compatibleSourceNodeTypes = [NodeTypeEnum.TEXT_TO_TEXT, NodeTypeEnum.PARALLELIZATION];
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
            :id="`${type}_prompt_${props.id}`"
            :position="props.type === 'source' ? Position.Bottom : Position.Top"
            :connectable="handleConnectableInputPrompt"
            style="background: #b2c7db"
            :style="props.style"
            class="z-10"
            :class="{
                handlebottom: props.type === 'source',
                handletop: props.type === 'target',
            }"
        />

        <UiGraphNodeUtilsDragArea
            :nodeId="props.id"
            :type="props.type"
            :compatibleSourceNodeTypes="compatibleSourceNodeTypes"
            :compatibleTargetNodeTypes="compatibleTargetNodeTypes"
            color="blue"
            orientation="horizontal"
        ></UiGraphNodeUtilsDragArea>
    </div>
</template>

<style scoped></style>
