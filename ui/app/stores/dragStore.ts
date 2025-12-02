import { defineStore } from 'pinia';
import type { NodeTypeEnum } from '@/types/enums';

export const useDragStore = defineStore('drag', () => {
    // Is a drag currently active anywhere in the graph?
    const isGlobalDragging = ref(false);

    // What type of node is being dragged? (Needed to check compatibility on mount)
    const draggedNodeType = ref<NodeTypeEnum | null>(null);
    const draggedNodeEdgesCount = ref<number>(0);

    const startDrag = (nodeType: NodeTypeEnum, edgesCount: number) => {
        draggedNodeType.value = nodeType;
        draggedNodeEdgesCount.value = edgesCount;
        isGlobalDragging.value = true;
    };

    const stopDrag = () => {
        isGlobalDragging.value = false;
        draggedNodeType.value = null;
        draggedNodeEdgesCount.value = 0;
    };

    return {
        isGlobalDragging,
        draggedNodeType,
        draggedNodeEdgesCount,
        startDrag,
        stopDrag,
    };
});
