import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NodeTypeEnum } from '@/types/enums';
import { useGraphChat } from '@/composables/useGraphChat';

const stubs = vi.hoisted(() => ({
    findNode: vi.fn((nodeId: string) => ({
        id: nodeId,
        position: { x: 100, y: 200 },
    })),
    placeBlock: vi.fn((options: { blocId: string }) => ({
        id: options.blocId === 'primary-prompt-text' ? 'attached-prompt-id' : 'chat-main-id',
    })),
    placeEdge: vi.fn(),
    resolveOverlaps: vi.fn(),
}));

vi.mock('@vue-flow/core', () => ({
    useVueFlow: () => ({ findNode: stubs.findNode }),
}));

mockNuxtImport('useRoute', () => () => ({ params: { id: 'graph-id' } }));
mockNuxtImport('useChatStore', () => () => ({}));
mockNuxtImport('storeToRefs', () => () => ({
    upcomingModelData: { value: { data: {} } },
}));
mockNuxtImport('useToast', () => () => ({ error: vi.fn() }));
mockNuxtImport('useGraphActions', () => () => ({
    placeBlock: stubs.placeBlock,
    placeEdge: stubs.placeEdge,
}));
mockNuxtImport('useGraphOverlaps', () => () => ({
    resolveOverlaps: stubs.resolveOverlaps,
}));

describe('useGraphChat createNodeFromVariant', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('resolves the main node and attached prompt below collisions after the placement delay', async () => {
        const { createNodeFromVariant } = useGraphChat();

        const createdNodes = createNodeFromVariant(
            NodeTypeEnum.TEXT_TO_TEXT,
            'source-node-id',
            [NodeTypeEnum.PROMPT],
            'Prompt text',
        );

        expect(createdNodes).toEqual({
            generatorNodeId: 'chat-main-id',
            promptNodeId: 'attached-prompt-id',
        });
        expect(stubs.resolveOverlaps).not.toHaveBeenCalled();

        await vi.advanceTimersByTimeAsync(1);

        expect(stubs.resolveOverlaps).toHaveBeenCalledOnce();
        expect(stubs.resolveOverlaps).toHaveBeenCalledWith(
            'chat-main-id',
            ['attached-prompt-id'],
            { direction: 'below' },
        );
    });
});
