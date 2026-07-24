import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Node } from '@vue-flow/core';
import { useGraphOverlaps } from '@/composables/useGraphOverlaps';

const stubs = vi.hoisted(() => ({
    nodes: { value: [] as Node[] },
    findNode: vi.fn(),
    updateNode: vi.fn(),
    isNodeIntersecting: vi.fn(),
    toastError: vi.fn(),
    getBlockByNodeType: vi.fn(() => ({ minSize: { width: 20, height: 20 } })),
}));

vi.mock('@vue-flow/core', () => ({
    useVueFlow: () => ({
        findNode: stubs.findNode,
        updateNode: stubs.updateNode,
        getNodes: stubs.nodes,
        isNodeIntersecting: stubs.isNodeIntersecting,
    }),
}));

mockNuxtImport('useRoute', () => () => ({ params: { id: 'graph-id' } }));
mockNuxtImport('useToast', () => () => ({ error: stubs.toastError }));
mockNuxtImport('useBlocks', () => () => ({ getBlockByNodeType: stubs.getBlockByNodeType }));

const node = (id: string, x: number, y: number, width = 20, height = 20): Node =>
    ({
        id,
        type: 'test-node',
        position: { x, y },
        dimensions: { width, height },
    }) as Node;

describe('useGraphOverlaps', () => {
    beforeEach(() => {
        stubs.nodes.value = [];
        stubs.findNode.mockReset();
        stubs.updateNode.mockReset();
        stubs.isNodeIntersecting.mockReset();
        stubs.toastError.mockReset();
        stubs.getBlockByNodeType.mockClear();
        stubs.findNode.mockImplementation((id: string | undefined) =>
            stubs.nodes.value.find((candidate) => candidate.id === id),
        );
        stubs.isNodeIntersecting.mockImplementation(
            (left: { x: number; y: number; width: number; height: number }, right: typeof left) =>
                left.x < right.x + right.width &&
                left.x + left.width > right.x &&
                left.y < right.y + right.height &&
                left.y + left.height > right.y,
        );
    });

    it('prunes far blockers, crosses bucket boundaries, and keeps first-blocker order', () => {
        const main = node('main', 500, 0);
        const far = node('far', 5000, 0);
        const first = node('first', 515, 0, 20, 20);
        const second = node('second', 510, 0, 20, 20);
        stubs.nodes.value = [main, far, first, second];

        useGraphOverlaps(ref('graph-id')).resolveOverlaps('main', [], {
            gap: 0,
            maxIterations: 1,
        });

        expect(main.position).toEqual({ x: 535, y: 0 });
        expect(stubs.updateNode).toHaveBeenCalledWith('main', { position: { x: 535, y: 0 } });
        expect(stubs.isNodeIntersecting).toHaveBeenCalledOnce();
    });

    it('moves attached nodes rigidly when only an attached member intersects', () => {
        const main = node('main', 0, 0);
        const attached = node('attached', 0, 100);
        const blocker = node('blocker', 10, 105);
        stubs.nodes.value = [main, attached, blocker];

        useGraphOverlaps(ref('graph-id')).resolveOverlaps(
            'main',
            ['attached', 'attached', undefined],
            { gap: 0, maxIterations: 1 },
        );

        expect(main.position).toEqual({ x: 30, y: 0 });
        expect(attached.position).toEqual({ x: 30, y: 100 });
        expect(stubs.updateNode).toHaveBeenCalledTimes(2);
    });

    it('preserves missing-main errors and no-blocker early return', () => {
        const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
        const overlaps = useGraphOverlaps(ref('graph-id'));

        overlaps.resolveOverlaps('missing', []);
        expect(consoleError).toHaveBeenCalledOnce();
        expect(stubs.toastError).toHaveBeenCalledOnce();

        stubs.nodes.value = [node('main', 0, 0), node('group-blocker', 0, 0)];
        overlaps.resolveOverlaps('main', []);
        expect(stubs.updateNode).not.toHaveBeenCalled();
    });

    it('preserves missing-attached and max-iteration warnings', () => {
        const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const main = node('main', 0, 0);
        const blocker = node('blocker', 0, 0, 1000, 20);
        stubs.nodes.value = [main, blocker];

        useGraphOverlaps(ref('graph-id')).resolveOverlaps('main', ['missing'], {
            gap: 0,
            maxIterations: 1,
        });

        expect(consoleWarn).toHaveBeenCalledTimes(2);
        expect(stubs.updateNode).toHaveBeenCalledOnce();
    });
});
