import type { GraphNode } from '@vue-flow/core';

export const graphNode = (
    node: Partial<GraphNode> & Pick<GraphNode, 'id'>,
): GraphNode => ({
    computedPosition: { x: 0, y: 0, z: 0 },
    handleBounds: { source: [], target: [] },
    dimensions: { width: 0, height: 0 },
    isParent: false,
    selected: false,
    resizing: false,
    dragging: false,
    data: {},
    events: {},
    type: 'test-node',
    position: { x: 0, y: 0 },
    ...node,
});
