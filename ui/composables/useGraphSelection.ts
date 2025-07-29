import type { GraphNode, Project, XYPosition } from '@vue-flow/core';

export function useGraphSelection(
    getNodes: Ref<GraphNode[]>,
    project: Project,
    addSelectedNodes: (nodes: GraphNode[]) => void,
    panBy: (delta: XYPosition) => boolean,
    isMouseOverRightSidebar: Ref<boolean>,
    isMouseOverLeftSidebar: Ref<boolean>,
) {
    const isSelecting = ref(false);
    const selectionRect = ref({ x: 0, y: 0, width: 0, height: 0 });
    const selectionStartPos = ref({ x: 0, y: 0 });
    const panAnimationId = ref<number | null>(null);
    const PAN_SPEED = 10; // pixels per frame

    const panOffset = ref({ x: 0, y: 0 });
    const lastMouseEvent = ref<MouseEvent | null>(null);

    const stopPanning = () => {
        if (panAnimationId.value !== null) {
            cancelAnimationFrame(panAnimationId.value);
            panAnimationId.value = null;
        }
    };

    const updateSelectionRect = (event: MouseEvent) => {
        if (!isSelecting.value) return;

        const { clientX, clientY } = event;
        const { x: startX, y: startY } = selectionStartPos.value;
        const { x: panX, y: panY } = panOffset.value;

        const effectiveClientX = clientX + panX;
        const effectiveClientY = clientY + panY;

        const dx = effectiveClientX - startX;
        const dy = effectiveClientY - startY;

        selectionRect.value = {
            x: dx > 0 ? startX - panX : effectiveClientX - panX,
            y: dy > 0 ? startY - panY : effectiveClientY - panY,
            width: Math.abs(dx),
            height: Math.abs(dy),
        };
    };

    const panStep = (direction: 'left' | 'right') => {
        panBy({ x: direction === 'left' ? -PAN_SPEED : PAN_SPEED, y: 0 });
        panOffset.value.x += direction === 'left' ? PAN_SPEED : -PAN_SPEED;
        if (lastMouseEvent.value) {
            updateSelectionRect(lastMouseEvent.value as MouseEvent);
        }
        panAnimationId.value = requestAnimationFrame(() => panStep(direction));
    };

    const startPanning = (direction: 'left' | 'right') => {
        if (panAnimationId.value !== null) return;
        panStep(direction);
    };

    const onSelectionMove = (event: MouseEvent) => {
        if (!isSelecting.value) return;

        lastMouseEvent.value = event;

        if (isMouseOverRightSidebar.value) {
            startPanning('left');
        } else if (isMouseOverLeftSidebar.value) {
            startPanning('right');
        } else {
            stopPanning();
        }

        updateSelectionRect(event);
    };

    const onSelectionEnd = () => {
        if (!isSelecting.value) return;

        stopPanning();
        isSelecting.value = false;

        window.removeEventListener('mousemove', onSelectionMove);
        window.removeEventListener('mouseup', onSelectionEnd);

        panOffset.value = { x: 0, y: 0 };
        lastMouseEvent.value = null;

        const start = project({ x: selectionRect.value.x, y: selectionRect.value.y });
        const end = project({
            x: selectionRect.value.x + selectionRect.value.width,
            y: selectionRect.value.y + selectionRect.value.height,
        });

        const selectionBBox = {
            x: Math.min(start.x, end.x),
            y: Math.min(start.y, end.y),
            x2: Math.max(start.x, end.x),
            y2: Math.max(start.y, end.y),
        };

        const selectedNodeIds = getNodes.value
            .filter((node) => {
                if (!node.position || !node.dimensions?.width || !node.dimensions?.height) {
                    return false;
                }
                const nodeBBox = {
                    x: node.position.x,
                    y: node.position.y,
                    x2: node.position.x + node.dimensions.width,
                    y2: node.position.y + node.dimensions.height,
                };
                return (
                    nodeBBox.x < selectionBBox.x2 &&
                    nodeBBox.x2 > selectionBBox.x &&
                    nodeBBox.y < selectionBBox.y2 &&
                    nodeBBox.y2 > selectionBBox.y
                );
            })
            .map((node) => node.id);

        if (selectedNodeIds.length) {
            addSelectedNodes(getNodes.value.filter((node) => selectedNodeIds.includes(node.id)));
        }

        selectionRect.value = { x: 0, y: 0, width: 0, height: 0 };
    };

    const onSelectionStart = (event: MouseEvent) => {
        getNodes.value.forEach((node) => (node.selected = false));
        isSelecting.value = true;
        selectionStartPos.value = { x: event.clientX, y: event.clientY };

        panOffset.value = { x: 0, y: 0 };
        lastMouseEvent.value = event;

        updateSelectionRect(event);

        window.addEventListener('mousemove', onSelectionMove);
        window.addEventListener('mouseup', onSelectionEnd);
    };

    onUnmounted(() => {
        window.removeEventListener('mousemove', onSelectionMove);
        window.removeEventListener('mouseup', onSelectionEnd);
    });

    return {
        isSelecting,
        selectionRect,
        onSelectionStart,
    };
}
