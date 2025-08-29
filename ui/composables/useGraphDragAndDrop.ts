import { useVueFlow, type Connection } from '@vue-flow/core';
import type { DragZoneHoverEvent } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';

interface DragData {
    blocId: string;
}

export function useGraphDragAndDrop() {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const { getBlockById } = useBlocks();
    const { error, warning } = useToast();
    const { placeBlock, placeEdge, numberOfConnectionsFromHandle } = useGraphActions();
    const { nodeTypeEnumToHandleCategory } = graphMappers();
    const { checkEdgeCompatibility } = useEdgeCompatibility();
    const graphEvents = useGraphEvents();

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
     * Handles the drag start event for a block.
     * This function sets the data to be transferred during the drag operation,
     * and emits an event indicating that a node drag has started.
     *
     * @param event - The DragEvent object containing information about the drag operation
     * @param blocId - The ID of the block being dragged
     * @throws Will log errors if DataTransfer is not available or if there are issues with the block definition
     */
    const onDragStart = (event: DragEvent, blocId: string) => {
        if (event.dataTransfer) {
            event.dataTransfer.setData('application/json', JSON.stringify({ blocId }));
            event.dataTransfer.effectAllowed = 'copy';
        } else {
            console.error('DataTransfer is not available.');
            error('Drag and drop is not supported in this browser.', {
                title: 'Drag and Drop Error',
            });
        }

        try {
            const blockDefinition = getBlockById(blocId);
            if (!blockDefinition || !blockDefinition.nodeType) {
                return;
            }
            graphEvents.emit('node-drag-start', { nodeType: blockDefinition?.nodeType });
        } catch (err) {
            console.error('Error during drag start:', err);
            error(
                'Error during drag start: ' +
                    (err instanceof Error ? err.message : '<unknown error>'),
                {
                    title: 'Error',
                },
            );
        }
    };

    /**
     * Handles the drag end event for a block.
     * This function emits an event indicating that a node drag has ended.
     *
     * @param event - The DragEvent object containing information about the drag operation
     * @param blocId - The ID of the block being dragged
     * @throws Will log errors if there are issues with the block definition
     */
    const onDragEnd = (event: DragEvent, blocId: string) => {
        try {
            const blockDefinition = getBlockById(blocId);
            if (!blockDefinition || !blockDefinition.nodeType) {
                return;
            }
            graphEvents.emit('node-drag-end', {});
        } catch (err) {
            console.error('Error during drag end:', err);
            error(
                'Error during drag end: ' +
                    (err instanceof Error ? err.message : '<unknown error>'),
                {
                    title: 'Error',
                },
            );
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
        const { project } = useVueFlow('main-graph-' + graphId.value);

        event.preventDefault();

        if ((event.target as HTMLElement).className.includes('drop-zone')) {
            return; // Ignore drops on the drag area
        }

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
            if (!dragData.blocId) {
                console.error('Drop failed: blocId missing in dragged data.');
                error('Drop failed: blocId missing in dragged data.', {
                    title: 'Error',
                });
                return;
            }

            const position = project({
                x: event.clientX,
                y: event.clientY,
            });

            placeBlock(graphId.value, dragData.blocId, position, { x: 0, y: 0 }, true);
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

    const onDropFromDragZone = (
        event: DragEvent,
        type: 'source' | 'target',
        nodeId: string,
        orientation: 'horizontal' | 'vertical',
    ) => {
        const { project, removeNodes, findNode } = useVueFlow('main-graph-' + graphId.value);

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

            // Parse the drag data from the event
            const dragData: DragData = JSON.parse(dataString);
            if (!dragData.blocId) {
                console.error('Drop failed: blocId missing in dragged data.');
                error('Drop failed: blocId missing in dragged data.', { title: 'Error' });
                return;
            }

            // Get the source rectangle and calculate the position for the new node
            const sourceRect = (event.target as HTMLElement).getBoundingClientRect();
            const position = project({
                x: sourceRect.left + sourceRect.width / 2,
                y: sourceRect.top + sourceRect.height / 2,
            });

            // Retrieve the block data and determine the position offset based on type and orientation
            const blockData = getBlockById(dragData.blocId);
            const dragBlockHandleCategory = nodeTypeEnumToHandleCategory(blockData?.nodeType);

            let positionOffset = { x: 0, y: 0 };
            if (orientation === 'horizontal') {
                positionOffset.y = type === 'source' ? 450 : -450;
                if (dragBlockHandleCategory === 'prompt') {
                    if (type === 'target') {
                        positionOffset.x = -250;
                        positionOffset.y = -175;
                    } else {
                        positionOffset.y = 150;
                    }
                }
            } else {
                positionOffset.x = type === 'source' ? 400 : -250;
                if (blockData?.nodeType === NodeTypeEnum.GITHUB) positionOffset.x -= 150;
            }

            // Place the block in the graph
            const newNode = placeBlock(
                graphId.value,
                dragData.blocId,
                position,
                positionOffset,
                true,
            );
            if (!newNode) {
                console.error('Failed to place new node.');
                error('Failed to place new node.', { title: 'Error' });
                return;
            }

            // Create and place the edge based on the type of drop (source or target)
            if (type === 'source') {
                const parentNode = findNode(nodeId);
                const handleCategory = nodeTypeEnumToHandleCategory(parentNode?.type);
                const targetHandleId = `${handleCategory}_${newNode?.id}`;
                placeEdge(graphId.value, nodeId, newNode?.id, null, targetHandleId);
            } else {
                const handleCategory = nodeTypeEnumToHandleCategory(newNode?.type);
                const targetHandleId = `${handleCategory}_${nodeId}`;
                const numberOfConnections = numberOfConnectionsFromHandle(
                    graphId.value,
                    nodeId,
                    targetHandleId,
                );

                if (numberOfConnections > 0) {
                    warning(
                        'This handle already has connections and does not support multiple connections.',
                        {
                            title: 'Warning',
                        },
                    );
                    removeNodes(newNode?.id);
                    return;
                }

                placeEdge(graphId.value, newNode?.id, nodeId, null, targetHandleId);
            }
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

    const offsetTable: Record<string, { x: number; y: number }> = {
        source_horizontal: { x: 0, y: 300 },
        source_vertical: { x: 200, y: 0 },
        target_horizontal: { x: 0, y: -300 },
        target_vertical: { x: -200, y: 0 },
    };

    const onDragStopOnDragZone = (
        currentHoveredZone: DragZoneHoverEvent | null,
        currentlyDraggedNodeId: string | null,
    ) => {
        const { getNodes } = useVueFlow('main-graph-' + graphId.value);

        if (currentHoveredZone && currentlyDraggedNodeId) {
            const { targetNodeId, targetHandleId, targetType, orientation } = currentHoveredZone;

            if (currentlyDraggedNodeId !== targetNodeId) {
                const handleTypeName = targetHandleId.split('_')[0];
                if (handleTypeName) {
                    const connection: Connection = {
                        source: targetType === 'source' ? targetNodeId : currentlyDraggedNodeId,
                        target: targetType === 'source' ? currentlyDraggedNodeId : targetNodeId,
                        sourceHandle:
                            targetType === 'source'
                                ? targetHandleId
                                : `${handleTypeName}_${currentlyDraggedNodeId}`,
                        targetHandle:
                            targetType === 'target'
                                ? targetHandleId
                                : `${handleTypeName}_${currentlyDraggedNodeId}`,
                    };

                    const numberOfConnections = numberOfConnectionsFromHandle(
                        graphId.value,
                        targetNodeId,
                        targetHandleId,
                    );

                    if (targetType === 'target' && numberOfConnections > 0) {
                        warning(
                            'This handle already has connections and does not support multiple connections.',
                            {
                                title: 'Warning',
                            },
                        );
                        return;
                    }

                    if (checkEdgeCompatibility(connection, getNodes.value, true)) {
                        const { x, y } = offsetTable[`${targetType}_${orientation}`] || {
                            x: 0,
                            y: 0,
                        };

                        const node = getNodes.value.find((n) => n.id === currentlyDraggedNodeId);
                        if (node) {
                            node.position.x += x;
                            node.position.y += y;
                        }

                        placeEdge(
                            graphId.value,
                            connection.source,
                            connection.target,
                            connection.sourceHandle,
                            connection.targetHandle,
                        );
                    }
                }
            }
        }
    };

    return {
        onDragStart,
        onDragEnd,
        onDragOver,
        onDropFromDragZone,
        onDragStopOnDragZone,
        onDrop,
    };
}
