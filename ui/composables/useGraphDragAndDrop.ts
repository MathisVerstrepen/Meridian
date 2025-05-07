import { useVueFlow, type Node } from '@vue-flow/core';

interface DragData {
    blocId: string;
}

export function useGraphDragAndDrop() {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const { getBlockById } = useBlocks();
    const { generateId } = useUniqueId();

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
            return;
        }

        try {
            const dataString = event.dataTransfer.getData('application/json');
            if (!dataString) {
                console.error('Drop failed: No application/json data found in dataTransfer.');
                return;
            }

            const dragData: DragData = JSON.parse(dataString);
            const blocId = dragData.blocId;

            if (!blocId) {
                console.error('Drop failed: blocId missing in dragged data.');
                return;
            }

            const draggedBlock = getBlockById(blocId);
            if (!draggedBlock) {
                console.error(`Drop failed: Block definition not found for ID: ${blocId}`);
                return;
            }

            const position = project({
                x: event.clientX,
                y: event.clientY,
            });

            // Adjust position to roughly center the node under the cursor
            const nodeWidthOffset = (draggedBlock.minSize?.width || 400) / 2;
            const nodeHeightOffset = (draggedBlock.minSize?.height || 200) / 2;
            position.x -= nodeWidthOffset;
            position.y -= nodeHeightOffset;

            const newNode: Node = {
                id: generateId(),
                type: draggedBlock.nodeType,
                position: position,
                label: draggedBlock.name,
                data: { ...draggedBlock.defaultData },
            };

            addNodes(newNode);
        } catch (error) {
            console.error('Error processing drop event:', error);
        }
    };

    return {
        onDragOver,
        onDrop,
    };
}
