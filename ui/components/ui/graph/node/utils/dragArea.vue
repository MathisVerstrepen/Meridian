<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

// --- Props ---
const props = defineProps<{
    nodeId: string;
    type: 'source' | 'target';
    orientation: 'horizontal' | 'vertical';
    compatibleSourceNodeTypes: NodeTypeEnum[];
    compatibleTargetNodeTypes: NodeTypeEnum[];
    color: 'heather' | 'golden' | 'blue';
}>();

// --- Composables ---
const graphEvents = useGraphEvents();
const { onDropFromDragZone } = useGraphDragAndDrop();

// --- Local State ---
const isDraggingOver = ref(false);
const isDragging = ref(false);

onMounted(async () => {
    const unsubscribeDragStart = graphEvents.on(
        'node-drag-start',
        ({ nodeType }: { nodeType: NodeTypeEnum }) => {
            if (
                (props.type === 'source' && !props.compatibleSourceNodeTypes.includes(nodeType)) ||
                (props.type === 'target' && !props.compatibleTargetNodeTypes.includes(nodeType))
            ) {
                return;
            }

            isDragging.value = true;
        },
    );

    const unsubscribeDragEnd = graphEvents.on('node-drag-end', () => {
        isDragging.value = false;
    });

    onUnmounted(unsubscribeDragStart);
    onUnmounted(unsubscribeDragEnd);
});
</script>

<template>
    <div
        class="bg-dried-heather/25 drag-area absolute z-0 backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'bg-dried-heather/25': color === 'heather',
            'bg-golden-ochre/25': color === 'golden',
            'bg-slate-blue/25': color === 'blue',

            'top-1/2 h-[80%] w-10 -translate-y-1/2': orientation === 'vertical',
            'left-1/2 h-10 w-[90%] -translate-x-1/2': orientation === 'horizontal',

            '!bg-dried-heather/50': isDraggingOver && color === 'heather',
            '!bg-golden-ochre/50': isDraggingOver && color === 'golden',
            '!bg-slate-blue/50': isDraggingOver && color === 'blue',

            'h-[85%] w-12': isDraggingOver && orientation === 'vertical',
            'h-12 w-[92%]': isDraggingOver && orientation === 'horizontal',

            'right-0 rounded-l-2xl': props.type === 'target' && orientation === 'vertical',
            'left-0 rounded-r-2xl': props.type === 'source' && orientation === 'vertical',
            'bottom-0 rounded-t-2xl': props.type === 'target' && orientation === 'horizontal',
            'top-0 rounded-b-2xl': props.type === 'source' && orientation === 'horizontal',
        }"
        v-if="isDragging"
        @dragover.prevent="isDraggingOver = true"
        @dragleave.prevent="isDraggingOver = false"
        @drop="
            (event) => {
                isDraggingOver = false;
                onDropFromDragZone(event, props.type, props.nodeId, props.orientation);
            }
        "
    ></div>
</template>

<style scoped></style>
