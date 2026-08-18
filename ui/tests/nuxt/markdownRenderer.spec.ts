import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import type { DOMWrapper } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
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
