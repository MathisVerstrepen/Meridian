import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import PresetPalette from '@/components/ui/settings/nodePresets/presetPalette.vue';

const blocks = [
    { id: 'prompt', nodeType: 'prompt', name: 'Prompt', desc: 'Add instructions', icon: 'prompt', color: '#fff' },
    { id: 'github', nodeType: 'github', name: 'GitHub', desc: 'Add repository context', icon: 'github', color: '#fff' },
];

mockNuxtImport('useBlocks', () => () => ({ blockDefinitions: ref({ inputs: blocks }) }));

describe('node preset block palette', () => {
    beforeEach(() => {
        vi.stubGlobal(
            'matchMedia',
            vi.fn(() => ({
                matches: false,
                addEventListener: vi.fn(),
                removeEventListener: vi.fn(),
            })),
        );
        vi.stubGlobal(
            'ResizeObserver',
            class {
                observe = vi.fn();
                unobserve = vi.fn();
                disconnect = vi.fn();
            },
        );
    });

    afterEach(() => vi.unstubAllGlobals());

    it('updates accessible controls at horizontal overflow boundaries', async () => {
        const wrapper = await mountSuspended(PresetPalette, {
            props: { nodeCount: 2, freePlan: false },
            global: { stubs: { UiIcon: defineComponent({ template: '<span />' }) } },
        });
        const scroller = wrapper.get('[data-testid="block-palette-scroller"]');
        const element = scroller.element as HTMLElement;
        const scrollBy = vi.fn();
        Object.defineProperties(element, {
            clientWidth: { configurable: true, value: 200 },
            scrollWidth: { configurable: true, value: 500 },
            scrollLeft: { configurable: true, value: 0, writable: true },
            scrollBy: { configurable: true, value: scrollBy },
        });

        await scroller.trigger('scroll');
        expect(wrapper.get('[aria-label="Scroll blocks left"]').attributes('disabled')).toBeDefined();
        expect(wrapper.get('[aria-label="Scroll blocks right"]').attributes('disabled')).toBeUndefined();

        await wrapper.get('[aria-label="Scroll blocks right"]').trigger('click');
        expect(scrollBy).toHaveBeenCalledWith({ left: 150, behavior: 'smooth' });

        element.scrollLeft = 300;
        await scroller.trigger('scroll');
        expect(wrapper.get('[aria-label="Scroll blocks left"]').attributes('disabled')).toBeUndefined();
        expect(wrapper.get('[aria-label="Scroll blocks right"]').attributes('disabled')).toBeDefined();
    });
});
