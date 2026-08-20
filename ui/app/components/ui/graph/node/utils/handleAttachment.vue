<script lang="ts" setup>
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import { getQuickWorkflowSlots } from '@/utils/quickWorkflow';
import { Position, useVueFlow } from '@vue-flow/core';

// --- Props ---
const props = withDefaults(
    defineProps<{
        type: 'source' | 'target';
        id: string;
        style?: Record<string, string>;
        isDragging: boolean;
        isVisible?: boolean;
        showQuickWorkflowWheel?: boolean;
    }>(),
    { style: () => ({}), showQuickWorkflowWheel: true },
);

// --- Stores ---
const dragStore = useDragStore();
const settingsStore = useSettingsStore();
const { blockSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();
const { snappedHandle } = useEdgeSnapping();
const { getNodes, getEdges } = useVueFlow();
const isHovering = ref(false);

const compatibleSourceNodeTypes = [
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
];
const compatibleTargetNodeTypes = [NodeTypeEnum.FILE_PROMPT, NodeTypeEnum.GITHUB];

// --- Computed ---
const isSnapped = computed(() => snappedHandle.value?.handleId === `attachment_${props.id}`);
const isConnectable = computed(() => {
    const node = getNodes.value.find((candidate) => candidate.id === props.id);
    return node
        ? handleConnectableInput(node, getEdges.value, NodeCategoryEnum.ATTACHMENT, props.type)
        : false;
});
const wheelOptions = computed(() =>
    getQuickWorkflowSlots(blockSettings.value, NodeCategoryEnum.ATTACHMENT, props.type),
);

// --- Lifecycle Hooks ---
</script>

<template>
    <div
        class="absolute top-0 z-20 flex h-full w-0 flex-col"
        :data-quick-workflow-handle="`${NodeCategoryEnum.ATTACHMENT}-${props.type}-${props.id}`"
        :class="{
            'left-0': props.type === 'target',
            'right-0': props.type === 'source',
        }"
        @mouseenter="isHovering = true"
        @mouseleave="isHovering = false"
    >
        <UiGraphNodeUtilsHandleCore
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
                    handleConnectableInput(
                        node,
                        connectedEdges,
                        NodeCategoryEnum.ATTACHMENT,
                        props.type,
                    )
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
        <UiGraphNodeUtilsWheel
            v-if="props.showQuickWorkflowWheel"
            :node-id="props.id"
            :options="wheelOptions"
            :is-hovering="isHovering"
            :category="NodeCategoryEnum.ATTACHMENT"
            :direction="props.type"
            :actionable="isConnectable"
            @update:is-hovering="isHovering = $event"
        />
    </div>
</template>

<style scoped></style>
