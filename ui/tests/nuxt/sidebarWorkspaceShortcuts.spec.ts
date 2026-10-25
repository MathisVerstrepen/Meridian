import { mountSuspended } from '@nuxt/test-utils/runtime';
import { afterEach, describe, expect, it, vi } from 'vitest';
import WorkspaceSwitcher from '@/components/ui/sidebar-history/sidebarHistoryWorkspacePagination.vue';
import type { Workspace } from '@/types/graph';

const workspaces: Workspace[] = Array.from({ length: 10 }, (_, index) => ({
    id: `workspace-${index + 1}`,
    name: `Workspace ${index + 1}`,
    created_at: '',
    updated_at: '',
}));

const mountSwitcher = (count = 10, activeIndex = 0) =>
    mountSuspended(WorkspaceSwitcher, {
        props: { workspaces: workspaces.slice(0, count), activeId: workspaces[activeIndex]!.id },
        attachTo: document.body,
    });

let wrapper: Awaited<ReturnType<typeof mountSwitcher>> | undefined;

afterEach(() => {
    wrapper?.unmount();
    wrapper = undefined;
});

const press = (options: KeyboardEventInit, target: EventTarget = window) => {
    const event = new KeyboardEvent('keydown', {
        altKey: true,
        bubbles: true,
        cancelable: true,
        ...options,
    });
    // Happy DOM reports AltGraph for every Alt press; model the separate modifier explicitly.
    const getModifierState = event.getModifierState.bind(event);
    vi.spyOn(event, 'getModifierState').mockImplementation((key) =>
        key === 'AltGraph' ? (options.modifierAltGraph ?? false) : getModifierState(key),
    );
    target.dispatchEvent(event);
    return event;
};

describe('sidebar workspace shortcuts', () => {
    it('shows workspace names and available shortcuts in title tooltips', async () => {
        wrapper = await mountSwitcher();
        const buttons = wrapper.findAll('button');
        expect(buttons[0]!.attributes('title')).toBe(
            'Workspace 1 (Alt+1; Alt+PageUp / Alt+PageDown)',
        );
        expect(buttons[8]!.attributes('aria-keyshortcuts')).toBe('Alt+9');
        expect(buttons[9]!.attributes('title')).toBe('Workspace 10 (Alt+PageUp / Alt+PageDown)');
        expect(buttons[9]!.attributes('aria-keyshortcuts')).toBeUndefined();
    });

    it('selects by physical digit key even when Alt changes its character', async () => {
        wrapper = await mountSwitcher();
        const event = press({ key: '™', code: 'Digit2' });
        expect(wrapper.emitted('select')).toEqual([['workspace-2']]);
        expect(event.defaultPrevented).toBe(true);
    });

    it('moves to adjacent workspaces beyond the first nine and stops at the ends', async () => {
        wrapper = await mountSwitcher(10, 8);
        press({ key: 'PageDown' });
        expect(wrapper.emitted('select')).toEqual([['workspace-10']]);
        await wrapper.setProps({ activeId: 'workspace-10' });
        press({ key: 'PageDown' });
        expect(wrapper.emitted('select')).toHaveLength(1);
        press({ key: 'PageUp' });
        expect(wrapper.emitted('select')?.at(-1)).toEqual(['workspace-9']);
        await wrapper.setProps({ activeId: 'workspace-1' });
        press({ key: 'PageUp' });
        expect(wrapper.emitted('select')).toHaveLength(2);
    });

    it.each([
        { altKey: false },
        { ctrlKey: true },
        { metaKey: true },
        { shiftKey: true },
        { repeat: true },
        { isComposing: true },
        { modifierAltGraph: true },
    ])('ignores unsupported modifiers and keyboard state: %j', async (options) => {
        wrapper = await mountSwitcher();
        const event = press({ key: '2', code: 'Digit2', ...options });
        expect(wrapper.emitted('select')).toBeUndefined();
        expect(event.defaultPrevented).toBe(false);
    });

    it('ignores handled events, unavailable workspaces, and unrelated keys', async () => {
        wrapper = await mountSwitcher(2);
        const handled = new KeyboardEvent('keydown', {
            key: '2',
            code: 'Digit2',
            altKey: true,
            cancelable: true,
        });
        handled.preventDefault();
        window.dispatchEvent(handled);
        expect(press({ key: '9', code: 'Digit9' }).defaultPrevented).toBe(false);
        expect(press({ key: 'n', code: 'KeyN' }).defaultPrevented).toBe(false);
        expect(wrapper.emitted('select')).toBeUndefined();
    });

    it.each(['input', 'textarea', 'select', 'contenteditable', 'textbox'])(
        'preserves typing in %s fields',
        async (kind) => {
            wrapper = await mountSwitcher();
            const field = document.createElement(
                ['contenteditable', 'textbox'].includes(kind) ? 'div' : kind,
            );
            if (kind === 'contenteditable') field.setAttribute('contenteditable', 'true');
            if (kind === 'textbox') field.setAttribute('role', 'textbox');
            document.body.append(field);
            try {
                expect(press({ key: '2', code: 'Digit2' }, field).defaultPrevented).toBe(false);
                expect(wrapper.emitted('select')).toBeUndefined();
            } finally {
                field.remove();
            }
        },
    );

    it('hides and disables the switcher with one workspace', async () => {
        wrapper = await mountSwitcher(1);
        expect(wrapper.find('button').exists()).toBe(false);
        expect(press({ key: '1', code: 'Digit1' }).defaultPrevented).toBe(false);
        expect(press({ key: 'PageDown' }).defaultPrevented).toBe(false);
        expect(wrapper.emitted('select')).toBeUndefined();
    });

    it('unregisters shortcuts when unmounted', async () => {
        wrapper = await mountSwitcher();
        wrapper.unmount();
        expect(press({ key: '2', code: 'Digit2' }).defaultPrevented).toBe(false);
        wrapper = undefined;
    });
});
