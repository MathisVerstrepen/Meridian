import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import type { Edge, GraphNode } from '@vue-flow/core';
import { computed, nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useGraphAutoLayout } from '@/composables/useGraphAutoLayout';

const stubs = vi.hoisted(() => ({
    nodes: { value: [] as GraphNode[] },
    edges: { value: [] as Edge[] },
    setNodes: vi.fn(),
    calculateGraphAutoLayout: vi.fn(),
    getBlockByNodeType: vi.fn(),
    saveGraph: vi.fn(),
    calls: [] as string[],
}));

vi.mock('@vue-flow/core', () => ({
    useVueFlow: () => ({
        getNodes: stubs.nodes,
        getEdges: stubs.edges,
        setNodes: stubs.setNodes,
    }),
}));

vi.mock('@/utils/graphAutoLayout', () => ({
    calculateGraphAutoLayout: stubs.calculateGraphAutoLayout,
}));

mockNuxtImport('useBlocks', () => () => ({
    getBlockByNodeType: stubs.getBlockByNodeType,
}));

mockNuxtImport('useCanvasSaveStore', () => () => ({
    saveGraph: stubs.saveGraph,
}));

const node = (id: string, overrides: Partial<GraphNode> = {}): GraphNode =>
    ({
        id,
        type: 'prompt',
        position: { x: 10, y: 20 },
        data: { marker: id },
        ...overrides,
    }) as GraphNode;

describe('useGraphAutoLayout', () => {
    beforeEach(() => {
        stubs.nodes.value = [];
        stubs.edges.value = [];
        stubs.calls.length = 0;
        stubs.setNodes.mockReset();
        stubs.setNodes.mockImplementation(() => {
            stubs.calls.push('setNodes');
            void nextTick(() => stubs.calls.push('nextTick'));
        });
        stubs.saveGraph.mockReset();
        stubs.saveGraph.mockImplementation(() => stubs.calls.push('saveGraph'));
        stubs.calculateGraphAutoLayout.mockReset();
        stubs.calculateGraphAutoLayout.mockReturnValue(new Map());
        stubs.getBlockByNodeType.mockReset();
        stubs.getBlockByNodeType.mockImplementation((type: string) =>
            type === 'prompt' ? { minSize: { width: 260, height: 270 } } : undefined,
        );
    });

    it('resolves each dimension fallback and forwards edge topology without mutation', async () => {
        const measured = node('measured', {
            dimensions: { width: 210, height: 0 },
            width: 999,
            height: 230,
            style: { width: '998px', height: '997px' },
        });
        const numeric = node('numeric', { width: 220, height: 230 });
        const styled = node('styled', {
            width: 0,
            height: Number.NaN,
            style: { width: '240px', height: '250.5px' },
        });
        const minimum = node('minimum');
        const safety = node('safety', { type: 'unknown' });
        const originalEdge: Edge = {
            id: 'edge',
            source: 'measured',
            target: 'numeric',
            sourceHandle: 'attachment_measured',
            targetHandle: 'attachment_numeric',
            data: { untouched: true },
        };
        const nullableHandleEdge: Edge = {
            id: 'nullable-edge',
            source: 'numeric',
            target: 'styled',
            sourceHandle: null,
            targetHandle: undefined,
        };
        stubs.nodes.value = [measured, numeric, styled, minimum, safety];
        stubs.edges.value = [originalEdge, nullableHandleEdge];
        const fitGraph = vi.fn().mockImplementation(() => stubs.calls.push('fitGraph'));

        const result = await useGraphAutoLayout({
            graphId: computed(() => 'graph-id'),
            fitGraph,
        }).autoLayoutGraph();

        const layoutNodes = stubs.calculateGraphAutoLayout.mock.calls[0]![0];
        expect(
            layoutNodes.map(
                ({ id, type, width, height, parentNode }: {
                    id: string;
                    type?: string;
                    width: number;
                    height: number;
                    parentNode?: string;
                }) => ({ id, type, width, height, parentNode }),
            ),
        ).toEqual([
            { id: 'measured', type: 'prompt', width: 210, height: 230, parentNode: undefined },
            { id: 'numeric', type: 'prompt', width: 220, height: 230, parentNode: undefined },
            { id: 'styled', type: 'prompt', width: 240, height: 250.5, parentNode: undefined },
            { id: 'minimum', type: 'prompt', width: 260, height: 270, parentNode: undefined },
            { id: 'safety', type: 'unknown', width: 100, height: 100, parentNode: undefined },
        ]);
        expect(stubs.calculateGraphAutoLayout.mock.calls[0]![1]).toEqual([
            {
                id: 'edge',
                source: 'measured',
                target: 'numeric',
                sourceHandle: 'attachment_measured',
                targetHandle: 'attachment_numeric',
            },
            {
                id: 'nullable-edge',
                source: 'numeric',
                target: 'styled',
                sourceHandle: null,
                targetHandle: undefined,
            },
        ]);
        expect(stubs.edges.value[0]).toBe(originalEdge);
        expect(stubs.edges.value[0]).toEqual(originalEdge);
        expect(stubs.edges.value[1]).toBe(nullableHandleEdge);
        expect(result).toBe(true);
        expect(stubs.setNodes).toHaveBeenCalledOnce();
        expect(fitGraph).toHaveBeenCalledOnce();
        expect(stubs.saveGraph).toHaveBeenCalledOnce();
        expect(stubs.calls).toEqual(['setNodes', 'nextTick', 'fitGraph', 'saveGraph']);
    });

    it('moves only returned outer roots in one ordered batch and preserves children', async () => {
        const group = node('group', { type: 'group', position: { x: 0, y: 0 }, selected: true });
        const child = node('child', {
            parentNode: 'group',
            position: { x: 30, y: 40 },
            dimensions: { width: 80, height: 90 },
        });
        const external = node('external', { position: { x: 500, y: 600 } });
        stubs.nodes.value = [child, group, external];
        stubs.calculateGraphAutoLayout.mockReturnValue(
            new Map([
                ['group', { x: 100, y: 200 }],
                ['external', { x: 300, y: 700 }],
            ]),
        );
        const fitGraph = vi.fn().mockImplementation(() => stubs.calls.push('fitGraph'));

        await useGraphAutoLayout({
            graphId: computed(() => 'graph-id'),
            fitGraph,
        }).autoLayoutGraph();

        expect(stubs.calculateGraphAutoLayout.mock.calls[0]![0]).toEqual([
            expect.objectContaining({ id: 'child', type: 'prompt', parentNode: 'group' }),
            expect.objectContaining({ id: 'group', type: 'group', parentNode: undefined }),
            expect.objectContaining({ id: 'external', type: 'prompt', parentNode: undefined }),
        ]);
        const updated = stubs.setNodes.mock.calls[0]![0] as GraphNode[];
        expect(updated.map(({ id }) => id)).toEqual(['child', 'group', 'external']);
        expect(updated[0]).toBe(child);
        expect(updated[0]).toEqual(child);
        expect(updated[1]).toEqual({ ...group, position: { x: 100, y: 200 } });
        expect(updated[1]?.selected).toBe(true);
        expect(updated[2]).toEqual({ ...external, position: { x: 300, y: 700 } });
        expect(stubs.setNodes).toHaveBeenCalledOnce();
        expect(fitGraph).toHaveBeenCalledOnce();
        expect(stubs.saveGraph).toHaveBeenCalledOnce();
        expect(stubs.calls).toEqual(['setNodes', 'nextTick', 'fitGraph', 'saveGraph']);
    });

    it('returns false without updating or fitting an empty graph', async () => {
        const fitGraph = vi.fn();

        const result = await useGraphAutoLayout({
            graphId: computed(() => 'graph-id'),
            fitGraph,
        }).autoLayoutGraph();

        expect(result).toBe(false);
        expect(stubs.calculateGraphAutoLayout).not.toHaveBeenCalled();
        expect(stubs.setNodes).not.toHaveBeenCalled();
        expect(fitGraph).not.toHaveBeenCalled();
        expect(stubs.saveGraph).not.toHaveBeenCalled();
    });

    it('propagates save failures after layout and fit complete', async () => {
        stubs.nodes.value = [node('prompt')];
        const failure = new Error('save failed');
        stubs.saveGraph.mockImplementation(async () => {
            stubs.calls.push('saveGraph');
            throw failure;
        });
        const fitGraph = vi.fn().mockImplementation(() => stubs.calls.push('fitGraph'));

        await expect(
            useGraphAutoLayout({
                graphId: computed(() => 'graph-id'),
                fitGraph,
            }).autoLayoutGraph(),
        ).rejects.toBe(failure);

        expect(stubs.saveGraph).toHaveBeenCalledOnce();
        expect(stubs.calls).toEqual(['setNodes', 'nextTick', 'fitGraph', 'saveGraph']);
    });
});
