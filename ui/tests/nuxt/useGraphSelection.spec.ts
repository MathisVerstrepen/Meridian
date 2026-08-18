import { ref, shallowRef } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphNode, Project } from '@vue-flow/core';
import { useGraphSelection } from '@/composables/useGraphSelection';
import { graphNode } from './support/graphNode';

const dragSelection = (
    selection: ReturnType<typeof useGraphSelection>,
    start: { x: number; y: number },
    end: { x: number; y: number },
) => {
    selection.onSelectionStart(new MouseEvent('mousedown', { clientX: start.x, clientY: start.y }));
    window.dispatchEvent(new MouseEvent('mousemove', { clientX: end.x, clientY: end.y }));
    window.dispatchEvent(new MouseEvent('mouseup'));
};

describe('useGraphSelection', () => {
    beforeEach(() => {
        vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
        vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined);
    });

    it('indexes current eligible geometry and preserves strict overlap and node order', () => {
        const parent = graphNode({ id: 'parent', position: { x: 100, y: 100 } });
        const nodes = shallowRef<GraphNode[]>([
            graphNode({
                id: 'first',
                position: { x: 35, y: 35 },
                dimensions: { width: 10, height: 10 },
            }),
            graphNode({
                id: 'child',
                parentNode: 'parent',
                position: { x: -90, y: -90 },
                dimensions: { width: 20, height: 20 },
            }),
            graphNode({
                id: 'edge-touch',
                position: { x: 50, y: 10 },
                dimensions: { width: 10, height: 10 },
            }),
            graphNode({
                id: 'group-node',
                position: { x: 10, y: 10 },
                dimensions: { width: 10, height: 10 },
            }),
            graphNode({ id: 'dimensionless', position: { x: 10, y: 10 } }),
            parent,
        ]);
        const selectedCalls: GraphNode[][] = [];
        const addSelectedNodes = (selectedNodes: GraphNode[]) => selectedCalls.push(selectedNodes);
        const project: Project = vi.fn((point: { x: number; y: number }) => point);
        const selection = useGraphSelection(
            nodes,
            project,
            addSelectedNodes,
            vi.fn(() => true),
            ref(false),
            ref(false),
        );

        dragSelection(selection, { x: 0, y: 0 }, { x: 50, y: 50 });

        expect(selectedCalls).toHaveLength(1);
        expect(selectedCalls[0]?.[0]).toBe(nodes.value[0]);
        expect(selectedCalls[0]?.[1]).toBe(nodes.value[1]);
        expect(nodes.value.every((node) => node.selected === false)).toBe(true);
    });

    it('projects reverse drags using completion-time geometry and skips empty callbacks', () => {
        const nodes = shallowRef<GraphNode[]>([
            graphNode({
                id: 'moving',
                position: { x: 100, y: 100 },
                dimensions: { width: 20, height: 20 },
            }),
        ]);
        const selectedCalls: GraphNode[][] = [];
        const addSelectedNodes = (selectedNodes: GraphNode[]) => selectedCalls.push(selectedNodes);
        const project: Project = vi.fn((point: { x: number; y: number }) => ({
            x: point.x - 100,
            y: point.y - 100,
        }));
        const selection = useGraphSelection(
            nodes,
            project,
            addSelectedNodes,
            vi.fn(() => true),
            ref(false),
            ref(false),
        );

        selection.onSelectionStart(new MouseEvent('mousedown', { clientX: 150, clientY: 150 }));
        nodes.value[0]!.position = { x: 25, y: 25 };
        window.dispatchEvent(new MouseEvent('mousemove', { clientX: 100, clientY: 100 }));
        window.dispatchEvent(new MouseEvent('mouseup'));
        expect(selectedCalls[0]?.[0]).toBe(nodes.value[0]);

        selectedCalls.length = 0;
        dragSelection(selection, { x: 300, y: 300 }, { x: 250, y: 250 });
        expect(selectedCalls).toHaveLength(0);
    });

    it('renders a delayed handoff move from the original pointer origin', () => {
        const nodes = shallowRef<GraphNode[]>([]);
        const selection = useGraphSelection(
            nodes,
            (point: { x: number; y: number }) => point,
            vi.fn(),
            vi.fn(() => true),
            ref(false),
            ref(false),
        );

        selection.onSelectionStart(
            new MouseEvent('mousedown', { clientX: 10, clientY: 20 }),
            new MouseEvent('mousemove', { clientX: 40, clientY: 65 }),
        );

        expect(selection.isSelecting.value).toBe(true);
        expect(selection.selectionRect.value).toEqual({ x: 10, y: 20, width: 30, height: 45 });
        window.dispatchEvent(new MouseEvent('mouseup'));
    });
});
