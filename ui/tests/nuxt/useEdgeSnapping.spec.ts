import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Position, type GraphNode } from '@vue-flow/core';
import { useEdgeSnapping } from '@/composables/useEdgeSnapping';
import { graphNode } from './support/graphNode';

interface GraphNodesState {
    value: GraphNode[];
}

interface GraphEdgesState {
    value: Array<{ targetHandle?: string | null }>;
}

const stubs = vi.hoisted(() => {
    const getNodes: GraphNodesState = { value: [] };
    const getEdges: GraphEdgesState = { value: [] };
    return {
        getNodes,
        getEdges,
        useGraphFlow: vi.fn(),
        acceptsMultipleInputEdges: vi.fn(() => true),
    };
});

mockNuxtImport('useGraphFlow', () => stubs.useGraphFlow);

mockNuxtImport('useEdgeCompatibility', () => () => ({
    acceptsMultipleInputEdges: stubs.acceptsMultipleInputEdges,
}));
mockNuxtImport('isSourceNodeTypeCompatibleWithTargetHandle', () => () => true);

const targetNode = (id: string, x: number, handleId: string): GraphNode =>
    graphNode({
        id,
        position: { x, y: 0 },
        handleBounds: {
            source: [],
            target: [{
                id: handleId,
                nodeId: id,
                x: 0,
                y: 0,
                width: 10,
                height: 10,
                type: 'target',
                position: Position.Left,
            }],
        },
    });

describe('useEdgeSnapping', () => {
    beforeEach(() => {
        stubs.getNodes.value = [
            graphNode({ id: 'source' }),
            targetNode('near', 100, 'near_input'),
            targetNode('far', 2000, 'far_input'),
        ];
        stubs.getEdges.value = [];
        stubs.useGraphFlow.mockReset();
        stubs.useGraphFlow.mockReturnValue({
            getNodes: stubs.getNodes,
            getEdges: stubs.getEdges,
        });
    });

    it('captures one indexed candidate snapshot at graph-ID drag start', () => {
        const snapping = useEdgeSnapping();
        const frames: FrameRequestCallback[] = [];
        vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
            frames.push(callback);
            return frames.length;
        });

        snapping.startSnapping({
            nodeId: 'source',
            handleId: 'source_output',
            handleType: 'source',
            graphId: 'graph-id',
        });
        stubs.getNodes.value = [graphNode({ id: 'source' }), targetNode('new', 1, 'new_input')];

        snapping.findNearestHandle({ x: 105, y: 5 }, 'graph-id');
        frames.shift()?.(0);

        expect(stubs.useGraphFlow).toHaveBeenCalledTimes(1);
        expect(snapping.snappedHandle.value).toMatchObject({
            nodeId: 'near',
            handleId: 'near_input',
        });
        snapping.stopSnapping();

        snapping.startSnapping({
            nodeId: 'source',
            handleId: 'source_output',
            handleType: 'source',
            graphId: 'graph-id',
        });
        snapping.findNearestHandle({ x: 5, y: 5 }, 'graph-id');
        frames.shift()?.(1);

        expect(stubs.useGraphFlow).toHaveBeenCalledTimes(2);
        expect(snapping.snappedHandle.value?.nodeId).toBe('new');
        snapping.stopSnapping();
    });

    it('keeps exact nearest and first-candidate tie behavior', () => {
        stubs.getNodes.value = [
            graphNode({ id: 'source' }),
            targetNode('first', -15, 'first_input'),
            targetNode('second', 5, 'second_input'),
        ];
        const snapping = useEdgeSnapping();
        const frames: FrameRequestCallback[] = [];
        vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
            frames.push(callback);
            return frames.length;
        });

        snapping.startSnapping({
            nodeId: 'source',
            handleId: 'source_output',
            handleType: 'source',
            graphId: 'graph-id',
        });
        snapping.findNearestHandle({ x: 0, y: 5 }, 'graph-id');
        frames.shift()?.(0);

        expect(snapping.snappedHandle.value?.nodeId).toBe('first');
        snapping.stopSnapping();
    });

    it('supports lazy cache construction and clears pending drag state on stop', () => {
        const snapping = useEdgeSnapping();
        const cancelAnimationFrame = vi.spyOn(window, 'cancelAnimationFrame');
        vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(42);

        snapping.startSnapping({
            nodeId: 'source',
            handleId: 'source_output',
            handleType: 'source',
        });
        expect(stubs.useGraphFlow).not.toHaveBeenCalled();

        snapping.findNearestHandle({ x: 105, y: 5 }, 'graph-id');
        snapping.stopSnapping();

        expect(cancelAnimationFrame).toHaveBeenCalledWith(42);
        expect(snapping.connectionSource.value).toBeNull();
        expect(snapping.snappedHandle.value).toBeNull();
    });
});
