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
        multipleInput?: boolean;
        isVisible?: boolean;
        showQuickWorkflowWheel?: boolean;
    }>(),
    {
        style: () => ({}),
        showQuickWorkflowWheel: true,
    },
);

// --- Stores ---
const dragStore = useDragStore();
const settingsStore = useSettingsStore();
const { blockSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { handleConnectableInput } = useEdgeCompatibility();
const { snappedHandle } = useEdgeSnapping();
const { getNodes, getEdges } = useVueFlow();

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
const isConnectable = computed(() => {
    const node = getNodes.value.find((candidate) => candidate.id === props.id);
    return node
        ? handleConnectableInput(
              node,
              getEdges.value,
              NodeCategoryEnum.CONTEXT,
              props.type,
              props.multipleInput ?? false,
          )
        : false;
});
const wheelOptions = computed(() =>
    getQuickWorkflowSlots(blockSettings.value, NodeCategoryEnum.CONTEXT, props.type),
);
</script>

<template>
    <div
        class="absolute left-0 flex h-0 w-full flex-col"
        :data-quick-workflow-handle="`${NodeCategoryEnum.CONTEXT}-${props.type}-${props.id}`"
        :class="{
            'top-0': props.type === 'target',
            'bottom-0': props.type === 'source',
        }"
        @mouseenter="isHovering = true"
        @mouseleave="isHovering = false"
    >
        <!-- The Vue Flow Handle -->
        <UiGraphNodeUtilsHandleCore
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
                        NodeCategoryEnum.CONTEXT,
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
            v-if="props.showQuickWorkflowWheel"
            :node-id="props.id"
            :options="wheelOptions"
            :is-hovering="isHovering"
            :category="NodeCategoryEnum.CONTEXT"
            :direction="props.type"
            :actionable="isConnectable"
            :anchor-offset="props.style.left"
            @update:is-hovering="isHovering = $event"
        />
    </div>
</template>

<style></style>
