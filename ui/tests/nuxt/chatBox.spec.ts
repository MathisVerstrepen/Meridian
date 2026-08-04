import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, h, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatBox from '@/components/ui/chat/chatBox.vue';
import { NodeTypeEnum } from '@/types/enums';

const stubs = vi.hoisted(() => ({
    callOrder: [] as string[],
    generateNew: vi.fn(),
    graphEmit: vi.fn(),
}));

vi.mock('@/composables/useChatGenerator', async () => {
    const { ref: vueRef } = await import('vue');

    return {
        useChatGenerator: () => ({
            isStreaming: vueRef(false),
            streamingSession: vueRef(null),
            generationError: vueRef(null),
            selectedNodeType: vueRef(NodeTypeEnum.STREAMING),
            generateNew: stubs.generateNew,
            generateFollowUp: vi.fn(),
            regenerate: vi.fn(),
            handleCancelStream: vi.fn(),
            restoreStreamingState: vi.fn(),
        }),
    };
});

vi.mock('@/composables/useMessageEditing', async () => {
    const { ref: vueRef } = await import('vue');

    return {
        useMessageEditing: () => ({
            currentEditModeIdx: vueRef(null),
            handleEditDone: vi.fn(),
        }),
    };
});

mockNuxtImport('storeToRefs', () => (store: object) => store);
mockNuxtImport('useChatStore', () => () => ({
    openChatId: ref('chat-id'),
    isFetching: ref(false),
    isCanvasReady: ref(false),
    lastOpenedChatId: ref('chat-id'),
    closeChat: vi.fn(),
    loadAndOpenChat: vi.fn(),
    getSession: vi.fn(() => ({ fromNodeId: null, messages: [] })),
}));
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

describe('chatBox manual message generation', () => {
    beforeEach(() => {
        stubs.callOrder.length = 0;
        stubs.graphEmit.mockReset().mockImplementation(() => {
            stubs.callOrder.push('open-upcoming-node-data');
        });
        stubs.generateNew.mockReset().mockImplementation(() => {
            stubs.callOrder.push('generate-new');
        });
    });

    it('opens upcoming node data before generating with unchanged arguments', async () => {
        const wrapper = await mountSuspended(ChatBox, {
            shallow: true,
            global: {
                stubs: {
                    UiChatTextInput: TextInputStub,
                },
            },
        });
        const message = 'Generate this';
        const files: FileSystemObject[] = [
            {
                id: 'file-id',
                name: 'reference.png',
                type: 'file',
                created_at: '2026-08-04T00:00:00Z',
                updated_at: '2026-08-04T00:00:00Z',
                cached: true,
            },
        ];

        try {
            wrapper.findComponent(TextInputStub).vm.$emit('generate', message, files);

            expect(stubs.graphEmit).toHaveBeenCalledOnce();
            expect(stubs.graphEmit).toHaveBeenCalledWith('open-upcoming-node-data', {});
            expect(stubs.generateNew).toHaveBeenCalledOnce();
            expect(stubs.generateNew).toHaveBeenCalledWith(null, message, files);
            expect(stubs.callOrder).toEqual(['open-upcoming-node-data', 'generate-new']);
        } finally {
            wrapper.unmount();
        }
    });
});
