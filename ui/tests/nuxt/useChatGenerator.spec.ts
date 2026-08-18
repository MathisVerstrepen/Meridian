import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { computed, shallowRef } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useChatGenerator } from '@/composables/useChatGenerator';
import type { ChatSession } from '@/types/chat';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

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
mockNuxtImport('useFiles', () => () => ({ fileToMessageContent: vi.fn() }));
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
        stubs.openChatId.value = 'existing-chat-id';
        stubs.createNodeFromVariant.mockReturnValue({
            generatorNodeId: 'generator-node-id',
            promptNodeId: 'prompt-node-id',
        });
        stubs.ensureSession.mockReturnValue({ type: NodeTypeEnum.TEXT_TO_TEXT });
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
