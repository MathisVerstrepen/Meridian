import { mountSuspended } from '@nuxt/test-utils/runtime';
import { describe, expect, it, vi } from 'vitest';
import MessageTeleport from '@/components/ui/chat/utils/messageTeleport.vue';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import type { Message, MessageContent } from '@/types/graph';

const createMessage = (role: MessageRoleEnum, content: MessageContent[]): Message => ({
    role,
    content,
    model: null,
    node_id: null,
    type: NodeTypeEnum.TEXT_TO_TEXT,
    data: null,
    usageData: null,
});

const createChatContainer = (messageCount: number) => {
    const chatContainer = document.createElement('div');
    const anchors = Array.from({ length: messageCount }, (_, index) => {
        const anchor = document.createElement('div');
        anchor.dataset.messageIndex = String(index);
        Object.defineProperties(anchor, {
            offsetTop: { value: index * 200 },
            offsetHeight: { value: 80 },
        });
        chatContainer.append(anchor);
        return anchor;
    });
    Object.defineProperties(chatContainer, {
        clientHeight: { value: 100 },
        scrollTop: { value: 0, writable: true },
    });
    return { anchors, chatContainer };
};

describe('messageTeleport', () => {
    it('renders one accessible line per user message and previews text on hover or focus', async () => {
        const messages = [
            createMessage(MessageRoleEnum.user, [{
                type: MessageContentTypeEnum.TEXT,
                text: '  First\n user message with   details  ',
            }]),
            createMessage(MessageRoleEnum.assistant, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'Assistant response',
            }]),
            createMessage(MessageRoleEnum.user, [{
                type: MessageContentTypeEnum.FILE,
                file: {
                    filename: 'brief.pdf',
                    file_data: 'encoded',
                },
            }]),
        ];
        const { chatContainer } = createChatContainer(messages.length);
        const wrapper = await mountSuspended(MessageTeleport, {
            props: { messages, chatContainer },
        });

        try {
            const buttons = wrapper.findAll('button');
            expect(buttons).toHaveLength(2);
            expect(wrapper.get('nav').attributes('aria-label')).toBe('User message navigator');
            expect(buttons[0]?.attributes('aria-label')).toBe(
                'Go to user message 1: First user message with details',
            );
            expect(buttons[1]?.attributes('aria-label')).toBe(
                'Go to user message 2: User message',
            );
            expect(buttons.every((button) => button.classes().includes('h-3'))).toBe(true);
            expect(buttons.every((button) => button.classes().includes('w-8'))).toBe(true);
            expect(wrapper.text()).toBe('');

            await buttons[0]?.trigger('mouseenter');
            expect(wrapper.text()).toContain('First user message with details');
            await buttons[0]?.trigger('mouseleave');
            expect(wrapper.text()).toBe('');

            await buttons[1]?.trigger('focus');
            expect(wrapper.text()).toContain('User message');
            await buttons[1]?.trigger('blur');
            expect(wrapper.text()).toBe('');
        } finally {
            wrapper.unmount();
        }
    });

    it('removes every embedded node ID marker while preserving surrounding preview text', async () => {
        const messages = [createMessage(MessageRoleEnum.user, [{
            type: MessageContentTypeEnum.TEXT,
            text: `Keep this opening text.

--- Node ID: 65f55e0a-0612-4fb3-91f4-e233fd2f13ea ---

Continue after first marker.
--- Node ID: a3c9471d-705b-411c-80ca-37fbe3d47e7a ---
Final thought.`,
        }])];
        const { chatContainer } = createChatContainer(messages.length);
        const wrapper = await mountSuspended(MessageTeleport, {
            props: { messages, chatContainer },
        });

        try {
            const button = wrapper.get('button');
            const expectedPreview =
                'Keep this opening text. Continue after first marker. Final thought.';

            expect(button.attributes('aria-label')).toBe(`Go to user message 1: ${expectedPreview}`);
            expect(button.attributes('aria-label')).not.toContain('Node ID');
            expect(button.attributes('aria-label')).not.toContain('65f55e0a');

            await button.trigger('mouseenter');
            expect(wrapper.text()).toBe(expectedPreview);
        } finally {
            wrapper.unmount();
        }
    });

    it('smoothly teleports to the exact user message and applies a transient highlight', async () => {
        const messages = [
            createMessage(MessageRoleEnum.user, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'First user message',
            }]),
            createMessage(MessageRoleEnum.assistant, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'Assistant response',
            }]),
            createMessage(MessageRoleEnum.user, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'Second user message',
            }]),
        ];
        const { anchors, chatContainer } = createChatContainer(messages.length);
        const scrollTo = vi.fn();
        chatContainer.scrollTo = scrollTo;
        const wrapper = await mountSuspended(MessageTeleport, {
            props: { messages, chatContainer },
        });

        try {
            await wrapper.findAll('button')[1]!.trigger('click');

            expect(wrapper.emitted('teleport')).toHaveLength(1);
            expect(scrollTo).toHaveBeenCalledOnce();
            expect(scrollTo).toHaveBeenCalledWith({ behavior: 'smooth', top: 384 });
            expect(anchors[0]?.classList.contains('highlight-teleport')).toBe(false);

            chatContainer.dispatchEvent(new Event('scroll'));
            await new Promise((resolve) => setTimeout(resolve, 110));
            expect(anchors[2]?.classList.contains('highlight-teleport')).toBe(true);

            anchors[2]?.dispatchEvent(new Event('animationend'));
            expect(anchors[2]?.classList.contains('highlight-teleport')).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('highlights without scrolling when the selected message already has the top inset', async () => {
        const messages = [
            createMessage(MessageRoleEnum.user, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'First user message',
            }]),
            createMessage(MessageRoleEnum.assistant, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'Assistant response',
            }]),
            createMessage(MessageRoleEnum.user, [{
                type: MessageContentTypeEnum.TEXT,
                text: 'Already inset',
            }]),
        ];
        const { anchors, chatContainer } = createChatContainer(messages.length);
        const scrollTo = vi.fn();
        chatContainer.scrollTop = 384;
        chatContainer.scrollTo = scrollTo;
        const wrapper = await mountSuspended(MessageTeleport, {
            props: { messages, chatContainer },
        });

        try {
            await wrapper.findAll('button')[1]!.trigger('click');

            expect(wrapper.emitted('teleport')).toHaveLength(1);
            expect(scrollTo).not.toHaveBeenCalled();
            expect(anchors[2]?.classList.contains('highlight-teleport')).toBe(true);

            anchors[2]?.dispatchEvent(new Event('animationend'));
            expect(anchors[2]?.classList.contains('highlight-teleport')).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('clamps the top inset at the scroll origin', async () => {
        const messages = [createMessage(MessageRoleEnum.user, [{
            type: MessageContentTypeEnum.TEXT,
            text: 'First user message',
        }])];
        const { anchors, chatContainer } = createChatContainer(messages.length);
        const scrollTo = vi.fn();
        chatContainer.scrollTo = scrollTo;
        const wrapper = await mountSuspended(MessageTeleport, {
            props: { messages, chatContainer },
        });

        try {
            await wrapper.get('button').trigger('click');

            expect(wrapper.emitted('teleport')).toHaveLength(1);
            expect(scrollTo).not.toHaveBeenCalled();
            expect(anchors[0]?.classList.contains('highlight-teleport')).toBe(true);

            anchors[0]?.dispatchEvent(new Event('animationend'));
            expect(anchors[0]?.classList.contains('highlight-teleport')).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('renders no navigator when there are no user messages', async () => {
        const messages = [createMessage(MessageRoleEnum.assistant, [{
            type: MessageContentTypeEnum.TEXT,
            text: 'Assistant response',
        }])];
        const { chatContainer } = createChatContainer(messages.length);
        const wrapper = await mountSuspended(MessageTeleport, {
            props: { messages, chatContainer },
        });

        try {
            expect(wrapper.find('nav').exists()).toBe(false);
            expect(wrapper.findAll('button')).toHaveLength(0);

            document.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'ArrowDown',
                ctrlKey: true,
            }));
            expect(wrapper.emitted('teleport')).toBeUndefined();
        } finally {
            wrapper.unmount();
        }
    });
});
