<script lang="ts" setup>
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import { getQuickWorkflowSlots } from '@/utils/quickWorkflow';
import { Position } from '@vue-flow/core';

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
const { getNodes, getEdges } = useGraphFlow();
const isHovering = ref(false);

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
const isConnectable = computed(() => {
    const node = getNodes.value.find((candidate) => candidate.id === props.id);
    return node
        ? handleConnectableInput(node, getEdges.value, NodeCategoryEnum.PROMPT, props.type)
        : false;
});
const wheelOptions = computed(() =>
    getQuickWorkflowSlots(blockSettings.value, NodeCategoryEnum.PROMPT, props.type),
);
</script>

<template>
    <div
        class="absolute left-0 z-20 flex h-0 w-full flex-col"
        :data-quick-workflow-handle="`${NodeCategoryEnum.PROMPT}-${props.type}-${props.id}`"
        :class="{
            'top-0': props.type === 'target',
            'bottom-0': props.type === 'source',
        }"
        @mouseenter="isHovering = true"
        @mouseleave="isHovering = false"
    >
        <UiGraphNodeUtilsHandleCore
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
                    handleConnectableInput(node, connectedEdges, NodeCategoryEnum.PROMPT, props.type)
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
        <UiGraphNodeUtilsWheel
            v-if="props.showQuickWorkflowWheel"
            :node-id="props.id"
            :options="wheelOptions"
            :is-hovering="isHovering"
            :category="NodeCategoryEnum.PROMPT"
            :direction="props.type"
            :actionable="isConnectable"
            :anchor-offset="props.style?.left"
            @update:is-hovering="isHovering = $event"
        />
    </div>
</template>

<style scoped></style>
