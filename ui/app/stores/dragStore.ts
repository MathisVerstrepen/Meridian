import { defineStore } from 'pinia';
import type { NodeTypeEnum } from '@/types/enums';

export const useDragStore = defineStore('drag', () => {
    // Is a drag currently active anywhere in the graph?
    const isGlobalDragging = ref(false);

    // What type of node is being dragged? (Needed to check compatibility on mount)
    const draggedNodeType = ref<NodeTypeEnum | null>(null);

    const startDrag = (nodeType: NodeTypeEnum) => {
        draggedNodeType.value = nodeType;
        isGlobalDragging.value = true;
    };

    const stopDrag = () => {
        isGlobalDragging.value = false;
        draggedNodeType.value = null;
    };

    return {
        isGlobalDragging,
        draggedNodeType,
        startDrag,
        stopDrag,
    };
});
