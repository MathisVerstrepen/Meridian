import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { computed, shallowRef } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useChatGenerator } from '@/composables/useChatGenerator';
import { DEFAULT_NODE_ID } from '@/constants';
import type { ChatSession } from '@/types/chat';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

const { useFiles: realUseFiles } = await vi.importActual<typeof import('@/composables/useFiles')>(
    '@/composables/useFiles',
);

const stubs = vi.hoisted(() => ({
    openChatId: { value: 'existing-chat-id' },
    upcomingModelData: { value: { data: { model: 'test-model' } } },
    addMessage: vi.fn(),
    getLatestMessage: vi.fn(),
    migrateSessionId: vi.fn(),
    removeAllMessagesFromIndex: vi.fn(),
    syncUpcomingModelDefaults: vi.fn(),
    saveGraph: vi.fn().mockResolvedValue(undefined),
    setChatCallback: vi.fn(),
    setOnFinishedCallback: vi.fn(),
    ensureSession: vi.fn(),
    removeChatCallback: vi.fn(),
    cancelStream: vi.fn(),
    retrieveCurrentSession: vi.fn(),
    isNodeStreaming: vi.fn(() => false),
    createNodeFromVariant: vi.fn(),
    waitForRender: vi.fn().mockResolvedValue(undefined),
    teleportViewportToNode: vi.fn(),
    execute: vi.fn().mockResolvedValue(undefined),
    error: vi.fn(),
    fileToMessageContent: vi.fn(),
}));

mockNuxtImport('useGraphFlow', () => () => ({
        getNodes: {
            value: [{ id: 'generator-node-id', data: { model: 'test-model' } }],
        },
    }));

mockNuxtImport('useChatStore', () => () => ({
    storeKind: 'chat',
    addMessage: stubs.addMessage,
    getLatestMessage: stubs.getLatestMessage,
    migrateSessionId: stubs.migrateSessionId,
    removeAllMessagesFromIndex: stubs.removeAllMessagesFromIndex,
    syncUpcomingModelDefaults: stubs.syncUpcomingModelDefaults,
}));
mockNuxtImport('useCanvasSaveStore', () => () => ({ saveGraph: stubs.saveGraph }));
mockNuxtImport('useStreamStore', () => () => ({
    storeKind: 'stream',
    setChatCallback: stubs.setChatCallback,
    setOnFinishedCallback: stubs.setOnFinishedCallback,
    ensureSession: stubs.ensureSession,
    removeChatCallback: stubs.removeChatCallback,
    cancelStream: stubs.cancelStream,
    retrieveCurrentSession: stubs.retrieveCurrentSession,
}));
mockNuxtImport('storeToRefs', () => (store: { storeKind: string }) =>
    store.storeKind === 'chat'
        ? {
              openChatId: stubs.openChatId,
              upcomingModelData: stubs.upcomingModelData,
          }
        : { isNodeStreaming: { value: stubs.isNodeStreaming } },
);
mockNuxtImport('useGraphChat', () => () => ({
    createNodeFromVariant: stubs.createNodeFromVariant,
    waitForRender: stubs.waitForRender,
}));
mockNuxtImport('useGraphActions', () => () => ({
    teleportViewportToNode: stubs.teleportViewportToNode,
}));
mockNuxtImport('useBlocks', () => () => ({
    getBlockByNodeType: (nodeType: NodeTypeEnum) => ({ nodeType }),
}));
mockNuxtImport('useMessage', () => () => ({
    getTextFromMessage: (message: Message) => message.content[0]?.text || '',
}));
mockNuxtImport('useFiles', () => () => ({ fileToMessageContent: stubs.fileToMessageContent }));
mockNuxtImport('useNodeRegistry', () => () => ({ execute: stubs.execute }));
mockNuxtImport('useToast', () => () => ({ error: stubs.error }));

const userMessage = (nodeId: string, text: string): Message => ({
    role: MessageRoleEnum.user,
    content: [{ type: MessageContentTypeEnum.TEXT, text }],
    model: 'test-model',
    node_id: nodeId,
    type: NodeTypeEnum.TEXT_TO_TEXT,
    data: { files: [] },
    usageData: null,
});

const setupGenerator = (messages: Message[]) => {
    const session = shallowRef<ChatSession>({
        fromNodeId: 'existing-chat-id',
        messages,
    });
    stubs.addMessage.mockImplementation((message: Message) => session.value.messages.push(message));
    stubs.getLatestMessage.mockImplementation(() => session.value.messages.at(-1));

    return {
        session,
        generator: useChatGenerator(
            session,
            computed(() => 'graph-id'),
            vi.fn(),
            vi.fn(),
        ),
    };
};

describe('useChatGenerator prompt identity', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.useFakeTimers();
        stubs.fileToMessageContent.mockReset().mockImplementation(realUseFiles().fileToMessageContent);
        stubs.openChatId.value = 'existing-chat-id';
        stubs.createNodeFromVariant.mockReturnValue({
            generatorNodeId: 'generator-node-id',
            promptNodeId: 'prompt-node-id',
        });
        stubs.ensureSession.mockReturnValue({ type: NodeTypeEnum.TEXT_TO_TEXT });
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it.each(['notes.txt', 'report.docx', 'picture.WEBP', 'scan.pdf'])(
        'executes a first message with %s after preparing its content', async (name) => {
            stubs.openChatId.value = DEFAULT_NODE_ID;
            const { session, generator } = setupGenerator([]);
            session.value.fromNodeId = DEFAULT_NODE_ID;
            generator.selectedNodeType.value = useBlocks().getBlockByNodeType(NodeTypeEnum.TEXT_TO_TEXT);
            const file: FileSystemObject = {
                id: 'stored-file-id', name, type: 'file', created_at: '', updated_at: '', cached: false,
            };

            expect(await generator.generateNew(null, {
                message: 'Read this', files: [file], githubContext: null,
            })).toBe(true);

            expect(session.value.messages[0]?.content).toEqual([
                { type: MessageContentTypeEnum.TEXT, text: 'Read this' },
                realUseFiles().fileToMessageContent(file),
            ]);
            expect(stubs.fileToMessageContent.mock.invocationCallOrder[0]).toBeLessThan(
                stubs.createNodeFromVariant.mock.invocationCallOrder[0]!,
            );
            expect(stubs.execute).toHaveBeenCalledExactlyOnceWith('generator-node-id');
            expect(generator.generationError.value).toBeNull();
        },
    );

    it('handles conversion failure before changing graph or chat state', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        stubs.fileToMessageContent.mockImplementationOnce(() => { throw new Error('Conversion failed'); });
        const { session, generator } = setupGenerator([]);
        generator.selectedNodeType.value = useBlocks().getBlockByNodeType(NodeTypeEnum.TEXT_TO_TEXT);

        expect(await generator.generateNew(null, {
            message: 'Keep this draft',
            files: [{ id: 'file', name: 'notes.txt', type: 'file', created_at: '', updated_at: '', cached: false }],
            githubContext: null,
        })).toBe(false);

        expect(stubs.createNodeFromVariant).not.toHaveBeenCalled();
        expect(stubs.addMessage).not.toHaveBeenCalled();
        expect(stubs.migrateSessionId).not.toHaveBeenCalled();
        expect(stubs.execute).not.toHaveBeenCalled();
        expect(session.value.fromNodeId).toBe('existing-chat-id');
        expect(stubs.openChatId.value).toBe('existing-chat-id');
        expect(generator.generationError.value).toContain('Please try again');
        expect(generator.isSubmitting.value).toBe(false);
        expect(stubs.error).not.toHaveBeenCalled();
    });

    it('reports missing executors inline without rejecting or adding a second toast', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => undefined);
        stubs.execute.mockRejectedValueOnce(new Error('No executor registered'));
        const { generator } = setupGenerator([]);
        generator.selectedNodeType.value = useBlocks().getBlockByNodeType(NodeTypeEnum.TEXT_TO_TEXT);

        await expect(generator.generateNew(null, {
            message: 'Hello', files: [], githubContext: null,
        })).resolves.toBe(false);

        expect(generator.generationError.value).toContain('Please try again');
        expect(generator.isSubmitting.value).toBe(false);
        expect(stubs.error).not.toHaveBeenCalled();
    });

    it('prevents repeated submissions while render readiness is pending', async () => {
        let finishRender = () => {};
        stubs.waitForRender.mockReturnValueOnce(new Promise<void>((resolve) => { finishRender = resolve; }));
        const { generator } = setupGenerator([]);
        generator.selectedNodeType.value = useBlocks().getBlockByNodeType(NodeTypeEnum.TEXT_TO_TEXT);
        const submission = { message: 'Hello', files: [], githubContext: null };
        const pending = generator.generateNew(null, submission);

        expect(generator.isSubmitting.value).toBe(true);
        expect(await generator.generateNew(null, submission)).toBe(false);
        expect(stubs.createNodeFromVariant).toHaveBeenCalledOnce();
        expect(stubs.execute).not.toHaveBeenCalled();
        finishRender();
        expect(await pending).toBe(true);
        expect(stubs.execute).toHaveBeenCalledOnce();
        expect(generator.isSubmitting.value).toBe(false);
    });

    it('stores both identities on a fresh follow-up while executing from the generator', async () => {
        const { session, generator } = setupGenerator([]);
        generator.selectedNodeType.value = useBlocks().getBlockByNodeType(
            NodeTypeEnum.TEXT_TO_TEXT,
        );

        await generator.generateNew(null, {
            message: 'Fresh prompt',
            files: [],
            githubContext: null,
        });

        const createdUserMessage = session.value.messages.find(
            (message) => message.role === MessageRoleEnum.user,
        );
        expect(createdUserMessage).toMatchObject({
            node_id: 'generator-node-id',
            prompt_node_id: 'prompt-node-id',
        });
        expect(session.value.fromNodeId).toBe('generator-node-id');
        expect(stubs.migrateSessionId).toHaveBeenCalledWith(
            'existing-chat-id',
            'generator-node-id',
        );
        expect(stubs.ensureSession).toHaveBeenCalledWith(
            'generator-node-id',
            NodeTypeEnum.TEXT_TO_TEXT,
        );
        expect(stubs.execute).toHaveBeenCalledWith('generator-node-id');
    });

    it('annotates the existing forced-initial user message without replacing generator identity', async () => {
        const existingMessage = userMessage('generator-node-id', 'Initial prompt');
        const { session, generator } = setupGenerator([existingMessage]);

        await generator.generateNew('generator-node-id');

        expect(existingMessage).toMatchObject({
            node_id: 'generator-node-id',
            prompt_node_id: 'prompt-node-id',
        });
        expect(session.value.fromNodeId).toBe('generator-node-id');
        expect(stubs.createNodeFromVariant).toHaveBeenCalledWith(
            NodeTypeEnum.TEXT_TO_TEXT,
            'existing-chat-id',
            {
                submission: {
                    message: 'Initial prompt',
                    files: [],
                    githubContext: null,
                },
                forcedNodeId: 'generator-node-id',
            },
        );
        expect(stubs.execute).toHaveBeenCalledWith('generator-node-id');
    });
});
