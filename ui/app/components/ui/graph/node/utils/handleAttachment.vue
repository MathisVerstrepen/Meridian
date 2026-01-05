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
];
const compatibleTargetNodeTypes = [NodeTypeEnum.FILE_PROMPT, NodeTypeEnum.GITHUB];

// --- Computed ---
const isSnapped = computed(() => snappedHandle.value?.handleId === `attachment_${props.id}`);

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
            class="z-30 transition-transform duration-200"
            :class="{
                'handleright origin-right': props.type === 'source',
                'handleleft origin-left': props.type === 'target',
                'translate-y-[12.5%] scale-125': isSnapped,
            }"
            :connectable="
                (node, connectedEdges) =>
                    handleConnectableInput(node, connectedEdges, 'attachment', props.type)
            "
        />

        <UiGraphNodeUtilsDragArea
            v-if="props.isVisible && dragStore.isGlobalDragging && !props.isDragging"
            :node-id="props.id"
            :type="props.type"
            :compatible-source-node-types="compatibleSourceNodeTypes"
            :compatible-target-node-types="compatibleTargetNodeTypes"
            color="heather"
            orientation="vertical"
            :handle-id="`attachment_${props.id}`"
        />
    </div>
</template>

<style scoped></style>
