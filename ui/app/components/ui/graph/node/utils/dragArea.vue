<script lang="ts" setup>
import type { NodeTypeEnum } from '@/types/enums';

// --- Props ---
const props = defineProps<{
    nodeId: string;
    type: 'source' | 'target';
    orientation: 'horizontal' | 'vertical';
    compatibleSourceNodeTypes: NodeTypeEnum[];
    compatibleTargetNodeTypes: NodeTypeEnum[];
    color: 'heather' | 'golden' | 'blue';
    handleId: string;
}>();

// --- Stores ---
const dragStore = useDragStore();

// --- Composables ---
const graphEvents = useGraphEvents();
const { onDropFromDragZone } = useGraphDragAndDrop();

// --- Local State ---
const isDraggingOver = ref(false);
const isCompatible = ref(false);

const checkCompatibility = () => {
    if (dragStore.draggedNodeEdgesCount > 0) {
        return false;
    }

    const nodeType = dragStore.draggedNodeType;
    if (!nodeType) return false;

    if (props.type === 'source') {
        return props.compatibleSourceNodeTypes.includes(nodeType);
    } else {
        return props.compatibleTargetNodeTypes.includes(nodeType);
    }
};

const handleMouseEnter = () => {
    if (isCompatible.value) {
        isDraggingOver.value = true;
        graphEvents.emit('drag-zone-hover', {
            targetNodeId: props.nodeId,
            targetHandleId: props.handleId,
            targetType: props.type,
            orientation: props.orientation,
        });
    }
};

const handleMouseLeave = () => {
    if (isCompatible.value) {
        isDraggingOver.value = false;
        graphEvents.emit('drag-zone-hover', null);
    }
};

onMounted(() => {
    isCompatible.value = checkCompatibility();
});
</script>

<template>
    <div
        v-show="isCompatible"
        class="drop-zone absolute z-0 shrink-0 duration-200 ease-in-out"
        :class="{
            active: isDraggingOver,

            'drop-zone-heather': color === 'heather',
            'drop-zone-golden': color === 'golden',
            'drop-zone-blue': color === 'blue',

            'top-1/2 h-[80%] w-10 -translate-y-1/2': orientation === 'vertical',
            'left-1/2 h-10 w-[90%] -translate-x-1/2': orientation === 'horizontal',

            'right-0 rounded-l-2xl': props.type === 'target' && orientation === 'vertical',
            'left-0 rounded-r-2xl': props.type === 'source' && orientation === 'vertical',
            'bottom-0 rounded-t-2xl': props.type === 'target' && orientation === 'horizontal',
            'top-0 rounded-b-2xl': props.type === 'source' && orientation === 'horizontal',
        }"
        @dragover.prevent="isDraggingOver = true"
        @dragleave.prevent="isDraggingOver = false"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
        @drop="
            (event) => {
                isDraggingOver = false;
                onDropFromDragZone(event, props.type, props.nodeId, props.orientation);
            }
        "
    />
</template>
