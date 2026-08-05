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
        vi.clearAllMocks();
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
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
