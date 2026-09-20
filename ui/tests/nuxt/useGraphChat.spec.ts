import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import type { GraphNode } from '@vue-flow/core';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';
import { NodeTypeEnum } from '@/types/enums';
import { useGraphChat } from '@/composables/useGraphChat';
import { graphNode } from './support/graphNode';

const stubs = vi.hoisted(() => {
    const nodes: GraphNode[] = [];
    const edges: Array<{ source: string; target: string }> = [];
    return {
    nodes: { value: nodes },
    edges: { value: edges },
    findNode: vi.fn((nodeId: string) =>
        stubs.nodes.value.find((node) => node.id === nodeId) ?? {
            id: nodeId,
            position: { x: 100, y: 200 },
        },
    ),
    placeBlock: vi.fn((options: { blocId: string }) => ({
        id:
            options.blocId === 'primary-prompt-text'
                ? 'attached-prompt-id'
                : options.blocId === 'primary-prompt-file'
                  ? 'attached-file-id'
                  : options.blocId === 'primary-github-context'
                    ? 'attached-github-id'
                    : 'chat-main-id',
    })),
    placeEdge: vi.fn(),
    resolveOverlaps: vi.fn(),
    areNodesInitialized: { value: false },
    onNodesInitialized: vi.fn<(callback: () => void) => { off: () => void }>(),
    off: vi.fn(),
    };
});

mockNuxtImport('useGraphFlow', () => () => ({
        findNode: stubs.findNode,
        getNodes: stubs.nodes,
        getEdges: stubs.edges,
        areNodesInitialized: stubs.areNodesInitialized,
        onNodesInitialized: stubs.onNodesInitialized,
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
mockNuxtImport('useBlocks', () => () => ({
    getBlockByNodeType: () => ({ minSize: { width: 100, height: 100 } }),
}));

describe('useGraphChat createNodeFromVariant', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers();
        stubs.nodes.value = [
            graphNode({
                id: 'source-node-id',
                type: NodeTypeEnum.TEXT_TO_TEXT,
                position: { x: 100, y: 200 },
            }),
        ];
        stubs.edges.value = [];
        const parentElement = document.createElement('div');
        parentElement.dataset.id = 'source-node-id';
        parentElement.style.height = '180px';
        document.body.append(parentElement);
    });

    afterEach(() => {
        vi.useRealTimers();
        document.body.replaceChildren();
    });

    it('places a generator below a generator parent without direct generator children', () => {
        const { createNodeFromVariant } = useGraphChat();

        createNodeFromVariant(NodeTypeEnum.TEXT_TO_TEXT, 'source-node-id', {
            submission: { message: 'Prompt text', files: [], githubContext: null },
        });

        expect(stubs.placeBlock).toHaveBeenCalledWith(
            expect.objectContaining({
                blocId: 'primary-model-text-to-text',
                positionFrom: { x: 100, y: 530 },
            }),
        );
    });

    it('places a generator right of the rightmost direct generator child', () => {
        stubs.nodes.value.push(
            graphNode({
                id: 'direct-child',
                type: NodeTypeEnum.ROUTING,
                position: { x: 500, y: 600 },
                dimensions: { width: 350, height: 100 },
            }),
            graphNode({
                id: 'descendant',
                type: NodeTypeEnum.PARALLELIZATION,
                position: { x: 1200, y: 1000 },
                width: 300,
            }),
        );
        stubs.edges.value = [
            { source: 'source-node-id', target: 'direct-child' },
            { source: 'direct-child', target: 'descendant' },
        ];
        const { createNodeFromVariant } = useGraphChat();

        createNodeFromVariant(NodeTypeEnum.ROUTING, 'source-node-id', {
            submission: { message: 'Prompt text', files: [], githubContext: null },
        });

        expect(stubs.placeBlock).toHaveBeenCalledWith(
            expect.objectContaining({
                blocId: 'primary-model-routing',
                positionFrom: { x: 1000, y: 600 },
            }),
        );
    });

    it('resolves the main node and attached prompt below collisions after the placement delay', async () => {
        const { createNodeFromVariant } = useGraphChat();

        const createdNodes = createNodeFromVariant(NodeTypeEnum.TEXT_TO_TEXT, 'source-node-id', {
            submission: { message: 'Prompt text', files: [], githubContext: null },
        });

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

    it('creates populated file and Git inputs in the same overlap group', async () => {
        const { createNodeFromVariant } = useGraphChat();
        const file = {
            id: 'file-id',
            name: 'notes.txt',
            type: 'file' as const,
            created_at: '',
            updated_at: '',
            cached: false,
        };
        const repoFile = { name: 'README.md', type: 'file' as const, path: 'README.md', children: [] };
        const repo = {
            provider: 'github',
            encoded_provider: 'github',
            full_name: 'meridian/test',
            description: null,
            clone_url_ssh: 'git@example.test:meridian/test.git',
            clone_url_https: 'https://example.test/meridian/test.git',
            default_branch: 'main',
        };

        createNodeFromVariant(NodeTypeEnum.TEXT_TO_TEXT, 'source-node-id', {
            submission: {
                message: 'Prompt text',
                files: [file],
                githubContext: {
                    repo,
                    selectedFiles: [repoFile],
                    selectedIssues: [],
                    currentBranch: 'feature',
                },
            },
        });

        expect(stubs.placeBlock).toHaveBeenCalledWith(
            expect.objectContaining({
                blocId: 'primary-github-context',
                data: {
                    repo,
                    files: [repoFile],
                    selectedIssues: [],
                    branch: 'feature',
                },
            }),
        );

        await vi.advanceTimersByTimeAsync(1);
        expect(stubs.resolveOverlaps).toHaveBeenCalledWith(
            'chat-main-id',
            ['attached-prompt-id', 'attached-file-id', 'attached-github-id'],
            { direction: 'below' },
        );
    });
});

describe('useGraphChat render readiness', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers();
        stubs.areNodesInitialized.value = false;
        stubs.onNodesInitialized.mockReset().mockReturnValue({ off: stubs.off });
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it('resolves already-initialized graphs without waiting for another event', async () => {
        stubs.areNodesInitialized.value = true;
        await useGraphChat().waitForRender();
        expect(stubs.onNodesInitialized).not.toHaveBeenCalled();
        expect(vi.getTimerCount()).toBe(0);
    });

    it('resolves on initialization and cleans up the listener and fallback timer', async () => {
        const resolved = vi.fn();
        const pending = useGraphChat().waitForRender().then(resolved);
        await nextTick();
        expect(resolved).not.toHaveBeenCalled();
        stubs.onNodesInitialized.mock.calls[0]![0]();
        await pending;
        expect(resolved).toHaveBeenCalledOnce();
        expect(stubs.off).toHaveBeenCalledOnce();
        expect(vi.getTimerCount()).toBe(0);
    });

    it('rechecks initialized state after subscribing to cover a missed event', async () => {
        stubs.onNodesInitialized.mockImplementationOnce(() => {
            stubs.areNodesInitialized.value = true;
            return { off: stubs.off };
        });
        await useGraphChat().waitForRender();
        expect(stubs.off).toHaveBeenCalledOnce();
        expect(vi.getTimerCount()).toBe(0);
    });

    it('allows execution to continue after a bounded wait when no event arrives', async () => {
        const resolved = vi.fn();
        const pending = useGraphChat().waitForRender().then(resolved);
        await nextTick();
        await vi.advanceTimersByTimeAsync(999);
        expect(resolved).not.toHaveBeenCalled();
        await vi.advanceTimersByTimeAsync(1);
        await pending;
        expect(resolved).toHaveBeenCalledOnce();
        expect(stubs.off).toHaveBeenCalledOnce();
        expect(vi.getTimerCount()).toBe(0);
    });
});
