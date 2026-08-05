import { mountSuspended } from '@nuxt/test-utils/runtime';
import { defineComponent, h } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import UploadButton from '@/components/ui/chat/attachment/uploadButton.vue';

const SlotStub = defineComponent({
    setup(_, { slots }) {
        return () => h('div', slots.default?.());
    },
});

const mountMenu = () =>
    mountSuspended(UploadButton, {
        global: {
            stubs: {
                Teleport: true,
                AnimatePresence: SlotStub,
                UiIcon: true,
            },
        },
    });

describe('chat add menu', () => {
    it('renders exact flat headings and actions in order', async () => {
        const wrapper = await mountMenu();
        await wrapper.get('button[aria-label="Add context"]').trigger('click');

        const labels = wrapper
            .findAll('li')
            .map((item) => item.text().trim())
            .filter(Boolean);
        expect(labels).toEqual([
            'Git',
            'Add files',
            'Add PR/issue',
            'Files',
            'From device',
            'From cloud',
        ]);

        expect(wrapper.findAll('ul')).toHaveLength(1);
        wrapper.unmount();
    });

    it('emits each Git and file action and closes after selection', async () => {
        const wrapper = await mountMenu();
        const addButton = wrapper.get('button[aria-label="Add context"]');

        await addButton.trigger('click');
        await wrapper.findAll('ul button')[0]!.trigger('click');
        expect(wrapper.emitted('add-git-context')).toEqual([['files']]);

        await addButton.trigger('click');
        const actionButtons = wrapper.findAll('ul button');
        await actionButtons[1]!.trigger('click');
        expect(wrapper.emitted('add-git-context')).toEqual([['files'], ['issues']]);

        await addButton.trigger('click');
        await wrapper.findAll('ul button').at(-1)!.trigger('click');
        expect(wrapper.emitted('open-cloud-select')).toHaveLength(1);

        await addButton.trigger('click');
        const input = wrapper.get('input[type="file"]');
        const fileList = { 0: new File(['test'], 'test.txt'), length: 1, item: () => null };
        Object.defineProperty(input.element, 'files', { value: fileList, configurable: true });
        await input.trigger('change');
        expect(wrapper.emitted('add-files')).toEqual([[fileList]]);
        wrapper.unmount();
    });

    it('does not open while disabled', async () => {
        const wrapper = await mountSuspended(UploadButton, {
            props: { disabled: true },
            global: { stubs: { Teleport: true, AnimatePresence: SlotStub, UiIcon: true } },
        });

        await wrapper.get('button[aria-label="Add context"]').trigger('click');
        expect(wrapper.find('ul').exists()).toBe(false);
        wrapper.unmount();
    });

    it('positions with untransformed dimensions fully above the button and clamps horizontally', async () => {
        const wrapper = await mountMenu();
        const addButton = wrapper.get('button[aria-label="Add context"]');
        vi.spyOn(addButton.element, 'getBoundingClientRect').mockReturnValue({
            top: 400,
            left: 900,
            right: 948,
            bottom: 448,
            width: 48,
            height: 48,
            x: 900,
            y: 400,
            toJSON: () => ({}),
        });
        const widthDescriptor = Object.getOwnPropertyDescriptor(
            HTMLElement.prototype,
            'offsetWidth',
        );
        const heightDescriptor = Object.getOwnPropertyDescriptor(
            HTMLElement.prototype,
            'offsetHeight',
        );
        Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
            configurable: true,
            get: () => 208,
        });
        Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
            configurable: true,
            get: () => 240,
        });

        try {
            await addButton.trigger('click');
            await wrapper.vm.$nextTick();

            const menu = wrapper.get('[data-add-context-menu]');
            expect(menu.attributes('style')).toContain('top: 152px');
            expect(menu.attributes('style')).toContain('left: 808px');
        } finally {
            if (widthDescriptor) {
                Object.defineProperty(HTMLElement.prototype, 'offsetWidth', widthDescriptor);
            }
            if (heightDescriptor) {
                Object.defineProperty(HTMLElement.prototype, 'offsetHeight', heightDescriptor);
            }
            wrapper.unmount();
        }
    });
});
