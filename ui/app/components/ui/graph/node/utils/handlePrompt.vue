<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import { Position, Handle } from '@vue-flow/core';

// --- Props ---
const props = defineProps<{
    type: 'source' | 'target';
    id: string;
    style?: Record<string, string>;
    isDragging: boolean;
    isVisible?: boolean;
}>();

// --- Stores ---
const dragStore = useDragStore();

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();
const { snappedHandle } = useEdgeSnapping();

const compatibleSourceNodeTypes = [
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
    NodeTypeEnum.PROMPT,
];
const compatibleTargetNodeTypes = [NodeTypeEnum.PROMPT];

// --- Computed ---
const isSnapped = computed(
    () =>
        snappedHandle.value?.handleId === `prompt_${props.id}` &&
        snappedHandle.value?.type === props.type,
);
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
            class="z-30 transition-transform duration-200"
            :class="{
                handlebottom: props.type === 'source',
                handletop: props.type === 'target',
                'translate-x-[12.5%] scale-125': isSnapped,
            }"
            :connectable="
                (node, connectedEdges) =>
                    handleConnectableInput(node, connectedEdges, 'prompt', props.type)
            "
        />

        <UiGraphNodeUtilsDragArea
            v-if="props.isVisible && dragStore.isGlobalDragging && !props.isDragging"
            :node-id="props.id"
            :type="props.type"
            :compatible-source-node-types="compatibleSourceNodeTypes"
            :compatible-target-node-types="compatibleTargetNodeTypes"
            color="blue"
            orientation="horizontal"
            :handle-id="`prompt_${props.id}`"
        />
    </div>
</template>

<style scoped></style>
