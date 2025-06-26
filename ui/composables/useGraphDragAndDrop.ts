import { useVueFlow } from '@vue-flow/core';

import type { NodeWithDimensions } from '@/types/graph';

interface DragData {
    blocId: string;
}

export function useGraphDragAndDrop() {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const { getBlockById } = useBlocks();
    const { generateId } = useUniqueId();
    const { error } = useToast();

    /**
     * Handler for the dragover event.
     * Prevents default browser behavior and sets the drop effect to 'copy'.
     * This visual indicator shows the user that dropping is allowed and will create a copy.
     *
     * @param event - The DragEvent object containing information about the drag operation
     */
    const onDragOver = (event: DragEvent) => {
        event.preventDefault();
        if (event.dataTransfer) {
            event.dataTransfer.dropEffect = 'copy';
        }
    };

    /**
     * Handles the drop event in the graph editor.
     *
     * This function processes a drag and drop operation by:
     * 1. Extracting the JSON data from the drop event
     * 2. Parsing the block ID from the dragged data
     * 3. Retrieving the block definition using the ID
     * 4. Calculating the drop position with appropriate offsets
     * 5. Creating and adding a new node to the graph
     *
     * @param event - The DOM drag event containing transfer data
     * @throws Will not throw errors but logs them to console
     * @remarks Position is adjusted to center the node under the cursor
     */
    const onDrop = (event: DragEvent) => {
        const { project, addNodes } = useVueFlow('main-graph-' + graphId.value);

        event.preventDefault();

        if (!event.dataTransfer) {
            console.error('Drop failed: DragEvent dataTransfer or Vue Flow instance is missing.');
            error('Drop failed: DragEvent dataTransfer or Vue Flow instance is missing.', {
                title: 'Error',
            });
            return;
        }

        try {
            const dataString = event.dataTransfer.getData('application/json');
            if (!dataString) {
                // This happen of other drop events are triggered, like a file drop
                return;
            }

            const dragData: DragData = JSON.parse(dataString);
            const blocId = dragData.blocId;

            if (!blocId) {
                console.error('Drop failed: blocId missing in dragged data.');
                error('Drop failed: blocId missing in dragged data.', {
                    title: 'Error',
                });
                return;
            }

            const draggedBlock = getBlockById(blocId);
            if (!draggedBlock) {
                console.error(`Drop failed: Block definition not found for ID: ${blocId}`);
                error(`Drop failed: Block definition not found for ID: ${blocId}`, {
                    title: 'Error',
                });
                return;
            }

            const position = project({
                x: event.clientX,
                y: event.clientY,
            });

            // Adjust position to roughly center the node under the cursor
            const nodeWidthOffset = draggedBlock.minSize.width / 2;
            const nodeHeightOffset = draggedBlock.minSize.height / 2;
            position.x -= nodeWidthOffset;
            position.y -= nodeHeightOffset;

            const newNode: NodeWithDimensions = {
                id: generateId(),
                type: draggedBlock.nodeType,
                position: position,
                label: draggedBlock.name,
                data: { ...draggedBlock.defaultData },
            };

            // Set dimensions if the block has forced initial dimensions
            if (draggedBlock?.forcedInitialDimensions) {
                newNode.width = draggedBlock.minSize.width;
                newNode.height = draggedBlock.minSize.height;
            }

            addNodes(newNode);
        } catch (err) {
            console.error('Error processing drop event:', err);
            error(
                'Error processing drop event: ' +
                    (err instanceof Error ? err.message : '<unknown error>'),
                {
                    title: 'Error',
                },
            );
        }
    };

    return {
        onDragOver,
        onDrop,
    };
}
