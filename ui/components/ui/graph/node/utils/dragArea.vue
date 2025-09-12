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
    selfNodeDragging: boolean;
    handleId: string;
}>();

// --- Composables ---
const graphEvents = useGraphEvents();
const { onDropFromDragZone } = useGraphDragAndDrop();

// --- Local State ---
const isDraggingOver = ref(false);
const isDragging = ref(false);

const handleMouseEnter = () => {
    if (isDragging.value) {
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
    if (isDragging.value) {
        isDraggingOver.value = false;
        graphEvents.emit('drag-zone-hover', null);
    }
};

onMounted(async () => {
    const unsubscribeDragStart = graphEvents.on(
        'node-drag-start',
        ({ nodeType, nEdges }: { nodeType: NodeTypeEnum; nEdges?: number }) => {
            if (
                (props.type === 'source' && !props.compatibleSourceNodeTypes.includes(nodeType)) ||
                (props.type === 'target' && !props.compatibleTargetNodeTypes.includes(nodeType)) ||
                (nEdges !== undefined && nEdges > 0)
            ) {
                return;
            }
            isDragging.value = true;
        },
    );

    const unsubscribeDragEnd = graphEvents.on('node-drag-end', () => {
        isDragging.value = false;
        isDraggingOver.value = false;
    });

    onUnmounted(() => {
        unsubscribeDragStart();
        unsubscribeDragEnd();
    });
});
</script>

<template>
    <div
        v-show="isDragging && !selfNodeDragging"
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
