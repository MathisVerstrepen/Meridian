import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { reactive, ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import ToolQuestionCard from '@/components/ui/chat/utils/toolQuestionCard.vue';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';

const mocks = vi.hoisted(() => ({
    sendMessage: vi.fn(),
    ensureSession: vi.fn(),
    setChatCallback: vi.fn(),
    resumeExistingStream: vi.fn(),
    clearToolQuestionError: vi.fn(),
}));

mockNuxtImport('useWebSocket', () => () => ({ sendMessage: mocks.sendMessage }));
mockNuxtImport('storeToRefs', () => (store: {
    openChatId?: string;
    toolQuestionErrors?: Map<string, string>;
}) => ({
    openChatId: ref(store.openChatId),
    toolQuestionErrors: ref(store.toolQuestionErrors),
}));
mockNuxtImport('useToolCallDetails', () => () => ({
    fetchToolCallDetail: vi.fn(async () => ({
        id: 'tool-1',
        tool_call_id: 'tool-1',
        node_id: 'node-1',
        model_id: 'model-1',
        tool_name: 'ask_user',
        status: 'pending_user_input',
        arguments: { title: 'Question', questions: [] },
        result: {},
        model_context_payload: '',
        created_at: null,
    })),
}));
mockNuxtImport('useChatStore', () => () => reactive({
    openChatId: 'node-1',
    getSession: () => ({
        fromNodeId: 'node-1',
        messages: [{
            role: MessageRoleEnum.assistant,
            content: [{ type: MessageContentTypeEnum.TEXT, text: '' }],
            model: 'model-1',
            node_id: 'node-1',
            type: NodeTypeEnum.TEXT_TO_TEXT,
            data: null,
            usageData: null,
        }],
    }),
}));
mockNuxtImport('useStreamStore', () => () => reactive({
    toolQuestionErrors: new Map<string, string>(),
    ensureSession: mocks.ensureSession,
    setChatCallback: mocks.setChatCallback,
    resumeExistingStream: mocks.resumeExistingStream,
    clearToolQuestionError: mocks.clearToolQuestionError,
}));

describe('ToolQuestionCard submission', () => {
    it('keeps the existing WebSocket payload and stream-resume calls', async () => {
        const answer = { question: { value: 'Answer' } };
        const wrapper = await mountSuspended(ToolQuestionCard, {
            props: { toolCallId: 'tool-1' },
            global: {
                stubs: {
                    ToolQuestionCardBase: {
                        emits: ['submit'],
                        template: '<button data-testid="submit" @click="$emit(\'submit\', answer)">Submit</button>',
                        setup: () => ({ answer }),
                    },
                },
            },
        });

        try {
            await vi.waitFor(() =>
                expect(wrapper.find('[data-testid="submit"]').exists()).toBe(true),
            );
            await wrapper.get('[data-testid="submit"]').trigger('click');
            expect(mocks.ensureSession).toHaveBeenCalledWith('node-1', NodeTypeEnum.TEXT_TO_TEXT);
            expect(mocks.setChatCallback).toHaveBeenCalledWith(
                'node-1',
                NodeTypeEnum.TEXT_TO_TEXT,
                expect.any(Function),
            );
            expect(mocks.resumeExistingStream).toHaveBeenCalledWith('node-1');
            expect(mocks.sendMessage).toHaveBeenCalledWith({
                type: 'submit_tool_response',
                payload: { tool_call_id: 'tool-1', node_id: 'node-1', answer },
            });
        } finally {
            wrapper.unmount();
        }
    });
});
