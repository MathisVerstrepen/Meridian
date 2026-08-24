import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, h, nextTick, ref, type Ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatBox from '@/components/ui/chat/chatBox.vue';
import { DEFAULT_NODE_ID } from '@/constants';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import type { ChatInputSubmission, ChatSession } from '@/types/chat';
import type { Message } from '@/types/graph';

interface ChatBoxTestStubs {
    callOrder: string[];
    generateNew: ReturnType<typeof vi.fn>;
    graphEmit: ReturnType<typeof vi.fn>;
    initialOpenChatId: string;
    openChatId: Ref<string | null> | null;
    session: ChatSession;
    sessionRef: Ref<ChatSession> | null;
}

const stubs = vi.hoisted((): ChatBoxTestStubs => ({
    callOrder: Array<string>(),
    generateNew: vi.fn(),
    graphEmit: vi.fn(),
    initialOpenChatId: 'chat-id',
    openChatId: null,
    session: {
        fromNodeId: 'chat-id',
        messages: [],
    },
    sessionRef: null,
}));

mockNuxtImport('useChatGenerator', () => (session: Ref<ChatSession>) => {
    stubs.sessionRef = session;
    return {
        isStreaming: ref(false),
        streamingSession: ref(null),
        generationError: ref(null),
        selectedNodeType: ref(NodeTypeEnum.STREAMING),
        generateNew: stubs.generateNew,
        generateFollowUp: vi.fn(),
        regenerate: vi.fn(),
        handleCancelStream: vi.fn(),
        restoreStreamingState: vi.fn(),
    };
});

mockNuxtImport('useMessageEditing', () => () => ({
            currentEditModeIdx: ref(null),
            handleEditDone: vi.fn(),
        }));

mockNuxtImport('storeToRefs', () => <Store extends Record<string, RuntimeValue>>(store: Store) => store);
mockNuxtImport('useChatStore', () => () => {
    const openChatId = ref<string | null>(stubs.initialOpenChatId);
    stubs.openChatId = openChatId;
    return {
        openChatId,
        isFetching: ref(false),
        isCanvasReady: ref(false),
        lastOpenedChatId: ref('chat-id'),
        closeChat: vi.fn(),
        loadAndOpenChat: vi.fn(),
        getSession: vi.fn(() => stubs.session),
    };
});
mockNuxtImport('useSidebarCanvasStore', () => () => ({
    isRightOpen: ref(false),
    isLeftOpen: ref(false),
}));
mockNuxtImport('useCanvasSaveStore', () => () => ({ ensureGraphSaved: vi.fn() }));
mockNuxtImport('useStreamStore', () => () => ({
    isNodeStreaming: ref(() => false),
    regenerateTitle: vi.fn(),
    removeChatCallback: vi.fn(),
}));
mockNuxtImport('useSettingsStore', () => () => ({
    generalSettings: ref({
        openChatViewOnNewCanvas: false,
        enableMessageCollapsing: false,
    }),
}));
mockNuxtImport('useWebSocket', () => () => ({
    isConnected: ref(true),
    isReconnecting: ref(false),
    connect: vi.fn(),
}));
mockNuxtImport('useGraphChat', () => () => ({ isCanvasEmpty: vi.fn(() => false) }));
mockNuxtImport('useChatScroll', () => () => ({
    goBackToBottom: vi.fn(),
    scrollToBottom: vi.fn(),
    triggerScroll: vi.fn(),
    handleScroll: vi.fn(),
    isLockedToBottom: ref(true),
}));
mockNuxtImport('useAPI', () => () => ({ persistGraph: vi.fn() }));
mockNuxtImport('useGraphEvents', () => () => ({
    emit: stubs.graphEmit,
    on: vi.fn(() => () => undefined),
}));
mockNuxtImport('useToast', () => () => ({ success: vi.fn(), error: vi.fn() }));
mockNuxtImport('useMessage', () => () => ({
    getTextFromMessage: vi.fn(() => ''),
    getTextFromMessageFast: vi.fn(() => ''),
}));
mockNuxtImport('useHydratedMediaQuery', () => () => ref(false));

const TextInputStub = defineComponent({
    name: 'UiChatTextInput',
    emits: ['generate'],
    setup() {
        return () => h('div');
    },
});

const MarkdownRendererStub = (props: { message: Message }) =>
    h('span', { class: 'message-text' }, props.message.content[0]?.text ?? '');

const NodeTypeIndicatorStub = defineComponent({
    name: 'UiChatNodeTypeIndicator',
    props: {
        nodeType: {
            type: String,
            required: true,
        },
    },
    setup() {
        return () => h('span');
    },
});

describe('chatBox manual message generation', () => {
    beforeEach(() => {
        stubs.callOrder.length = 0;
        stubs.initialOpenChatId = 'chat-id';
        stubs.openChatId = null;
        stubs.session.fromNodeId = 'chat-id';
        stubs.session.messages.splice(0);
        stubs.sessionRef = null;
        stubs.graphEmit.mockReset().mockImplementation(() => {
            stubs.callOrder.push('open-upcoming-node-data');
        });
        stubs.generateNew.mockReset().mockImplementation(() => {
            stubs.callOrder.push('generate-new');
        });
    });

    it('opens upcoming node data before forwarding the typed submission', async () => {
        const wrapper = await mountSuspended(ChatBox, {
            shallow: true,
            global: {
                stubs: {
                    UiChatTextInput: TextInputStub,
                },
            },
        });
        const submission: ChatInputSubmission = {
            message: 'Generate this',
            files: [{
                id: 'file-id',
                name: 'reference.png',
                type: 'file',
                created_at: '2026-08-04T00:00:00Z',
                updated_at: '2026-08-04T00:00:00Z',
                cached: true,
            }],
            githubContext: null,
        };

        try {
            wrapper.findComponent(TextInputStub).vm.$emit('generate', submission);

            expect(stubs.graphEmit).toHaveBeenCalledOnce();
            expect(stubs.graphEmit).toHaveBeenCalledWith('open-upcoming-node-data', {});
            expect(stubs.generateNew).toHaveBeenCalledOnce();
            expect(stubs.generateNew).toHaveBeenCalledWith(null, submission);
            expect(stubs.callOrder).toEqual(['open-upcoming-node-data', 'generate-new']);
        } finally {
            wrapper.unmount();
        }
    });

    it('renders nested streamed text after migrating the temporary session', async () => {
        stubs.initialOpenChatId = DEFAULT_NODE_ID;
        stubs.session.fromNodeId = DEFAULT_NODE_ID;
        const wrapper = await mountSuspended(ChatBox, {
            shallow: true,
            global: {
                stubs: {
                    UiChatMarkdownRenderer: MarkdownRendererStub,
                    UiChatNodeTypeIndicator: NodeTypeIndicatorStub,
                    UiChatTextInput: TextInputStub,
                },
            },
        });

        const generatedNodeId = 'generated-node-id';
        const assistantMessage: Message = {
            role: MessageRoleEnum.assistant,
            content: [{ type: MessageContentTypeEnum.TEXT, text: '' }],
            model: 'test-model',
            node_id: generatedNodeId,
            type: NodeTypeEnum.TEXT_TO_TEXT,
            data: null,
            usageData: null,
        };
        const activeSession = stubs.sessionRef;
        const openChatId = stubs.openChatId;
        expect(activeSession).not.toBeNull();
        expect(openChatId).not.toBeNull();
        if (!activeSession || !openChatId) return;

        activeSession.value.fromNodeId = generatedNodeId;
        activeSession.value.messages.push(assistantMessage);
        openChatId.value = generatedNodeId;
        await nextTick();

        expect(wrapper.find('.message-text').exists()).toBe(true);
        expect(wrapper.text()).not.toContain('First streamed chunk');

        const textContent = activeSession.value.messages[0]?.content[0];
        expect(textContent?.type).toBe(MessageContentTypeEnum.TEXT);
        if (!textContent || textContent.type !== MessageContentTypeEnum.TEXT) return;
        textContent.text += 'First streamed chunk';
        await nextTick();

        expect(wrapper.text()).toContain('First streamed chunk');
    });
});
