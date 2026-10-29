import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import type { DOMWrapper } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { defineComponent, h } from 'vue';
import MarkdownRenderer from '@/components/ui/chat/markdownRenderer.vue';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

mockNuxtImport('useMessage', () => () => ({
    getTextFromMessage: (message: Message) => message.content[0]?.text || '',
    getFilesFromMessage: () => [],
    getImageUrlsFromMessage: () => [],
}));
mockNuxtImport('useToast', () => () => ({ error: vi.fn() }));
mockNuxtImport('useAPI', () => () => ({ getToolCallDetail: vi.fn() }));

const GENERATOR_ID = '11111111-1111-1111-1111-111111111111';
const PROMPT_ID = '22222222-2222-2222-2222-222222222222';
const FIRST_TAG_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
const SECOND_TAG_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

const createMessage = (text: string, promptNodeId?: string | null): Message => ({
    role: MessageRoleEnum.user,
    content: [{ type: MessageContentTypeEnum.TEXT, text }],
    model: 'test-model',
    node_id: GENERATOR_ID,
    prompt_node_id: promptNodeId,
    type: NodeTypeEnum.TEXT_TO_TEXT,
    data: null,
    usageData: null,
});

const mountRenderer = (message: Message) =>
    mountSuspended(MarkdownRenderer, {
        props: {
            message,
            editMode: true,
        },
        global: {
            stubs: {
                GeneratedImageCard: true,
                SandboxArtifactDownload: true,
                SandboxHtmlArtifactCard: true,
                ToolQuestionCard: true,
                VisualiseArtifactEmbed: true,
                UiChatAttachmentFiles: true,
                UiChatAttachmentImages: true,
                UiChatGithubFileChatInlineGroup: true,
                UiChatUtilsGeneratedImageLightbox: true,
                UiChatUtilsGeneratedImageLoader: true,
                UiChatUtilsToolCallDetailModal: true,
            },
        },
    });

const editZone = async (zone: Omit<DOMWrapper<Element>, 'exists'>, text: string) => {
    requireElement(zone.element, HTMLElement).innerText = text;
    await zone.trigger('input');
    await zone.trigger('keydown', { key: 'Enter' });
};

describe('markdownRenderer edit target identity', () => {
    it('prefers fresh prompt identity for untagged messages', async () => {
        const wrapper = await mountRenderer(createMessage('Fresh prompt', PROMPT_ID));

        try {
            await editZone(wrapper.get('[contenteditable]'), 'Edited fresh prompt');
            expect(wrapper.emitted('edit-done')).toEqual([[PROMPT_ID, 'Edited fresh prompt']]);
        } finally {
            wrapper.unmount();
        }
    });

    it('keeps legacy generator fallback when prompt identity is absent', async () => {
        const wrapper = await mountRenderer(createMessage('Legacy prompt'));

        try {
            await editZone(wrapper.get('[contenteditable]'), 'Edited legacy prompt');
            expect(wrapper.emitted('edit-done')).toEqual([[GENERATOR_ID, 'Edited legacy prompt']]);
        } finally {
            wrapper.unmount();
        }
    });

    it('lets reload-style tags override stale local identities', async () => {
        const wrapper = await mountRenderer(
            createMessage(`--- Node ID: ${FIRST_TAG_ID} ---\nReloaded prompt`, PROMPT_ID),
        );

        try {
            await editZone(wrapper.get('[contenteditable]'), 'Edited reloaded prompt');
            expect(wrapper.emitted('edit-done')).toEqual([
                [FIRST_TAG_ID, 'Edited reloaded prompt'],
            ]);
        } finally {
            wrapper.unmount();
        }
    });

    it('emits only the selected second tagged zone identity and text', async () => {
        const wrapper = await mountRenderer(
            createMessage(
                `--- Node ID: ${FIRST_TAG_ID} ---\nFirst prompt\n--- Node ID: ${SECOND_TAG_ID} ---\nSecond prompt`,
                PROMPT_ID,
            ),
        );

        try {
            const zones = wrapper.findAll('[contenteditable]');
            expect(zones).toHaveLength(2);
            await editZone(zones[1]!, 'Edited second prompt');
            expect(wrapper.emitted('edit-done')).toEqual([
                [SECOND_TAG_ID, 'Edited second prompt'],
            ]);
        } finally {
            wrapper.unmount();
        }
    });
});

describe('markdownRenderer legacy context display', () => {
    it('hides payload from both channels and tool activities while preserving the message', async () => {
        const hidden = `<tool_call_context id="old">
[ERROR]PRIVATE_ERROR[!ERROR]
<executing_code id="hidden">PRIVATE_CODE</executing_code>
<asking_user id="hidden">PRIVATE_QUESTION</asking_user>
<generating_image id="hidden">Prompt: "PRIVATE_IMAGE"</generating_image>
<search_query id="hidden">PRIVATE_SEARCH</search_query>
[THINK]PRIVATE_THOUGHT[!THINK]
</tool_call_context>`;
        const text = `Before ${hidden} After\n[THINK]Visible thought ${hidden} continues[!THINK]`;
        const message = { ...createMessage(text), role: MessageRoleEnum.assistant };
        const wrapper = await mountRenderer(message);
        try {
            await wrapper.setProps({ editMode: false });
            await vi.waitFor(() => expect(wrapper.text()).toContain('Before  After'));
            expect(wrapper.find('[data-testid="markdown-renderer-tool-activities"]').exists()).toBe(false);
            await wrapper.get('[data-testid="thinking-disclosure-button"]').trigger('click');
            await vi.waitFor(() => expect(wrapper.text()).toContain('Visible thought  continues'));
            expect(wrapper.html()).not.toMatch(/PRIVATE_|tool_call_context/);
            expect(message.content[0]?.text).toBe(text);
        } finally {
            wrapper.unmount();
        }
    });

    it('finalizes the same raw prefix without losing ordinary response text', async () => {
        const message = { ...createMessage('Visible <tool_call_con'), role: MessageRoleEnum.assistant };
        const wrapper = await mountRenderer(message);
        try {
            await wrapper.setProps({ editMode: false, isStreaming: true });
            await vi.waitFor(() => expect(wrapper.get('[data-testid="markdown-renderer-response"]').text()).toBe('Visible'));
            await wrapper.setProps({ isStreaming: false });
            await vi.waitFor(() => expect(wrapper.get('[data-testid="markdown-renderer-response"]').text()).toBe('Visible <tool_call_con'));
            expect(message.content[0]?.text).toBe('Visible <tool_call_con');
        } finally {
            wrapper.unmount();
        }
    });
});


describe('assistant activity placement', () => {
    it('places subagent activity after thoughts and before the main answer', async () => {
        const message = {
            ...createMessage('[THINK]Check the evidence[!THINK]\nFinal answer'),
            role: MessageRoleEnum.assistant,
            type: NodeTypeEnum.AGENT,
        };
        const wrapper = await mountSuspended(MarkdownRenderer, {
            props: { message, editMode: false },
            slots: { activity: () => h('div', { 'data-testid': 'agent-activity' }, 'Subagent') },
        });
        try {
            await vi.waitFor(() =>
                expect(wrapper.get('[data-testid="markdown-renderer-response"]').text())
                    .toContain('Final answer'),
            );
            const thinking = wrapper.get('[data-testid="thinking-disclosure-button"]').element;
            const activity = wrapper.get('[data-testid="agent-activity"]').element;
            const answer = wrapper.get('[data-testid="markdown-renderer-response"]').element;
            expect(
                thinking.compareDocumentPosition(activity) & Node.DOCUMENT_POSITION_FOLLOWING,
            ).toBeTruthy();
            expect(
                activity.compareDocumentPosition(answer) & Node.DOCUMENT_POSITION_FOLLOWING,
            ).toBeTruthy();
        } finally {
            wrapper.unmount();
        }
    });
});


describe('concurrent Agent renderers', () => {
    it('keeps diagnostics isolated when multiple results share a graph node', async () => {
        const message = { ...createMessage('Shared node output'), role: MessageRoleEnum.assistant };
        const ConcurrentResponses = defineComponent(() => () => h('div', [
            h(MarkdownRenderer, { message, editMode: false }),
            h(MarkdownRenderer, { message, editMode: false }),
        ]));
        const wrapper = await mountSuspended(ConcurrentResponses);
        try {
            await vi.waitFor(() => {
                const responses = wrapper.findAll('[data-testid="markdown-renderer-response"]');
                expect(responses).toHaveLength(2);
                expect(responses.every((response) => response.text() === 'Shared node output')).toBe(true);
            });
        } finally { wrapper.unmount(); }
    });
});
