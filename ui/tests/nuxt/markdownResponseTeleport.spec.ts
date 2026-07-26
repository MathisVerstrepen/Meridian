import { mount } from '@vue/test-utils';
import { defineComponent, h, Teleport } from 'vue';
import { describe, expect, it } from 'vitest';

const TeleportHarness = defineComponent({
    props: {
        scope: { type: String, required: true },
        label: { type: String, required: true },
    },
    setup(props) {
        return () =>
            h('div', [
                h('div', { innerHTML: `<div id="target-${props.scope}"></div>` }),
                h(
                    Teleport,
                    { to: `#target-${props.scope}`, defer: true },
                    h('button', { 'data-owner': props.scope }, props.label),
                ),
            ]);
    },
});

describe('deferred response token Teleports', () => {
    it('resolves same-update v-html targets and keeps parallel scopes isolated', () => {
        const wrapper = mount(
            defineComponent({
                setup: () => () =>
                    h('main', [
                        h(TeleportHarness, { scope: 'first', label: 'First' }),
                        h(TeleportHarness, { scope: 'second', label: 'Second' }),
                    ]),
            }),
            { attachTo: document.body },
        );

        try {
            expect(document.querySelector('#target-first')?.textContent).toBe('First');
            expect(document.querySelector('#target-second')?.textContent).toBe('Second');
            expect(document.querySelector('#target-first [data-owner="second"]')).toBeNull();
        } finally {
            wrapper.unmount();
        }
    });
});
