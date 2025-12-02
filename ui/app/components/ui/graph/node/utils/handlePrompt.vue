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

// --- Stores ---
const dragStore = useDragStore();

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
            :id="`prompt_${props.id}`"
            :type="props.type"
            :position="props.type === 'source' ? Position.Bottom : Position.Top"
            style="background: var(--color-node-cat-prompt)"
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
            v-if="dragStore.isGlobalDragging"
            :node-id="props.id"
            :type="props.type"
            :compatible-source-node-types="compatibleSourceNodeTypes"
            :compatible-target-node-types="compatibleTargetNodeTypes"
            color="blue"
            orientation="horizontal"
            :self-node-dragging="props.isDragging"
            :handle-id="`prompt_${props.id}`"
        />
    </div>
</template>

<style scoped></style>
