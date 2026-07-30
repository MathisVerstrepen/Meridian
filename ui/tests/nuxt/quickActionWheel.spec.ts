import { mountSuspended } from '@nuxt/test-utils/runtime';
import { afterEach, describe, expect, it, vi } from 'vitest';

import QuickActionWheel from '@/components/ui/graph/quickActionWheel.vue';
import type { GraphQuickAction } from '@/composables/useGraphQuickActions';

const actions: GraphQuickAction[] = [
    { id: 'first', label: 'First action', icon: 'first', run: () => undefined },
    {
        id: 'submenu',
        label: 'More actions',
        icon: 'more',
        children: [{ id: 'child', label: 'Child action', icon: 'child', run: () => undefined }],
    },
    { id: 'delete', label: 'Delete', icon: 'delete', danger: true, run: () => undefined },
];

const addNodeActions: GraphQuickAction[] = [
    {
        id: 'add-node',
        label: 'Add node',
        icon: 'add',
        childrenDisplay: 'external-fan',
        children: [
            {
                id: 'add-prompt',
                label: 'Prompt',
                icon: 'prompt',
                accentColor: '#c46a4a',
                run: () => undefined,
            },
            {
                id: 'add-generator',
                label: 'Generator',
                icon: 'generator',
                accentColor: '#61758a',
                run: () => undefined,
            },
        ],
    },
    { id: 'run-all', label: 'Run all', icon: 'run', run: () => undefined },
    { id: 'fit-graph', label: 'Fit graph', icon: 'fit', run: () => undefined },
];

const multipleFanActions: GraphQuickAction[] = [
    addNodeActions[0]!,
    {
        id: 'presets',
        label: 'Presets',
        icon: 'presets',
        childrenDisplay: 'external-fan',
        children: [
            {
                id: 'preset-one',
                label: 'Long accessible preset name',
                icon: 'preset',
                run: () => undefined,
            },
        ],
    },
    addNodeActions[1]!,
];

afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = '';
});

describe('quickActionWheel', () => {
    it('provides roving focus, submenu navigation, activation, and Escape dismissal', async () => {
        const wrapper = await mountSuspended(QuickActionWheel, {
            attachTo: document.body,
            props: { actions, x: 5, y: 5 },
            global: { stubs: { UiIcon: true } },
        });

        const menu = document.querySelector<HTMLElement>('[role="menu"]');
        expect(menu).not.toBeNull();
        expect(menu?.style.left).toBe('208px');
        expect(document.activeElement?.getAttribute('data-action-id')).toBe('first');
        const rootSegments = document.querySelectorAll<HTMLButtonElement>(
            '[data-root-quick-action-segment]',
        );
        expect(rootSegments).toHaveLength(3);
        expect(
            Array.from(rootSegments, (segment) => segment.style.clipPath).every((clipPath) =>
                clipPath.startsWith('url('),
            ),
        ).toBe(true);
        expect(
            Array.from(document.querySelectorAll('[id^="quick-action-root-segment-"] path')).every(
                (path) => path.getAttribute('d')?.includes(' A '),
            ),
        ).toBe(true);
        expect(document.querySelector('[data-testid="quick-action-root-rim"]')).not.toBeNull();
        expect(
            document.querySelector('[data-testid="quick-action-root-rim"]')?.classList.contains('z-10'),
        ).toBe(true);
        expect(Array.from(rootSegments).every((segment) => segment.className.includes('backdrop-blur-xl'))).toBe(
            true,
        );
        expect(Array.from(rootSegments, (segment) => segment.getAttribute('data-action-id'))).toEqual([
            'first',
            'submenu',
            'delete',
        ]);
        const dangerSegment = document.querySelector<HTMLElement>('[data-action-id="delete"]')!;
        expect(dangerSegment.dataset.dangerAction).toBe('true');
        expect(dangerSegment.className).toContain('text-terracotta-clay');

        menu?.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
        await nextTick();
        expect(document.activeElement?.getAttribute('data-action-id')).toBe('submenu');

        (document.activeElement as HTMLButtonElement).click();
        await nextTick();
        expect(document.querySelector('[data-action-id="child"]')).not.toBeNull();
        expect(document.querySelectorAll('[data-root-quick-action-segment]')).toHaveLength(1);
        expect(document.querySelector('button[aria-label="Back to previous quick actions"]')).not.toBeNull();

        (document.querySelector('[data-action-id="child"]') as HTMLButtonElement).click();
        expect(wrapper.emitted('activate')?.[0]?.[0]).toMatchObject({ id: 'child' });

        menu?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        expect(wrapper.emitted('close')).toHaveLength(1);
        wrapper.unmount();
    });

    it('returns from a submenu with Backspace and dismisses on outside pointerdown', async () => {
        const wrapper = await mountSuspended(QuickActionWheel, {
            attachTo: document.body,
            props: { actions, x: 500, y: 500 },
            global: { stubs: { UiIcon: true } },
        });
        const menu = document.querySelector<HTMLElement>('[role="menu"]')!;
        (document.querySelector('[data-action-id="submenu"]') as HTMLButtonElement).click();
        await nextTick();
        menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
        await nextTick();
        expect(document.querySelector('[data-action-id="first"]')).not.toBeNull();

        document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
        expect(wrapper.emitted('close')).toHaveLength(1);
        wrapper.unmount();
    });

    it('opens the Add node arc on hover without flicker and supports explicit keyboard entry', async () => {
        const wrapper = await mountSuspended(QuickActionWheel, {
            attachTo: document.body,
            props: { actions: addNodeActions, x: 5, y: 5 },
            global: { stubs: { UiIcon: true } },
        });
        vi.useFakeTimers();
        const menu = document.querySelector<HTMLElement>('[role="menu"]')!;
        const addNode = document.querySelector<HTMLButtonElement>('[data-action-id="add-node"]')!;
        const rootClipPaths = Array.from(
            document.querySelectorAll<HTMLButtonElement>('[data-quick-action]:not([data-external-quick-action])'),
            (button) => button.style.clipPath,
        );

        expect(menu.style.left).toBe('304px');
        const mainOuterRadius = Number(menu.dataset.mainOuterRadius);
        const outerInnerRadius = Number(menu.dataset.outerInnerRadius);
        const outerRadius = Number(menu.dataset.wheelOuterRadius);
        const outerLabelRadius = Number(menu.dataset.outerLabelRadius);
        expect(mainOuterRadius - outerInnerRadius).toBe(2);
        expect(outerLabelRadius).toBeGreaterThan((mainOuterRadius + outerRadius) / 2);
        expect(outerLabelRadius).toBeLessThan(outerRadius);
        expect(document.activeElement).toBe(addNode);
        expect(document.querySelectorAll('[data-external-quick-action]')).toHaveLength(0);

        addNode.dispatchEvent(new PointerEvent('pointerenter'));
        await nextTick();

        expect(document.querySelectorAll('[data-external-quick-action]')).toHaveLength(2);
        expect(document.querySelector('[data-testid="quick-action-external-connector"]')).toBeNull();
        expect(document.querySelector('[data-testid="quick-action-external-rim"]')).not.toBeNull();
        expect(
            document.querySelector('[data-testid="quick-action-external-rim"]')?.classList.contains('z-0'),
        ).toBe(true);
        expect(
            Array.from(document.querySelectorAll<HTMLElement>('[data-external-quick-action]')).every((segment) =>
                segment.className.includes('backdrop-blur-xl'),
            ),
        ).toBe(true);
        const externalSegments = Array.from(
            document.querySelectorAll<HTMLElement>('[data-external-quick-action]'),
        );
        expect(externalSegments.map((segment) => segment.style.getPropertyValue('--quick-action-accent'))).toEqual([
            '#c46a4a',
            '#61758a',
        ]);
        expect(externalSegments.every((segment) => segment.classList.contains('z-0'))).toBe(true);
        expect(
            Array.from(document.querySelectorAll<HTMLElement>('[data-root-quick-action-segment]')).every((segment) =>
                segment.classList.contains('z-10'),
            ),
        ).toBe(true);
        expect(document.querySelector('[data-action-id="run-all"]')).not.toBeNull();
        expect(document.querySelector('[data-action-id="fit-graph"]')).not.toBeNull();
        expect(addNode.getAttribute('aria-expanded')).toBe('true');
        expect(
            Array.from(
                document.querySelectorAll<HTMLButtonElement>(
                    '[data-quick-action]:not([data-external-quick-action])',
                ),
                (button) => button.style.clipPath,
            ),
        ).toEqual(rootClipPaths);

        const firstChild = document.querySelector<HTMLButtonElement>('[data-action-id="add-prompt"]')!;
        addNode.dispatchEvent(new PointerEvent('pointerleave'));
        firstChild.dispatchEvent(new PointerEvent('pointerenter'));
        vi.advanceTimersByTime(200);
        await nextTick();
        expect(document.querySelectorAll('[data-external-quick-action]')).toHaveLength(2);

        firstChild.dispatchEvent(new PointerEvent('pointerleave'));
        vi.advanceTimersByTime(200);
        await nextTick();
        expect(document.querySelectorAll('[data-external-quick-action]')).toHaveLength(0);

        addNode.click();
        await nextTick();
        await nextTick();
        expect(document.activeElement?.getAttribute('data-action-id')).toBe('add-prompt');

        menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
        await nextTick();
        expect(document.querySelectorAll('[data-external-quick-action]')).toHaveLength(0);
        expect(document.activeElement).toBe(addNode);

        addNode.click();
        await nextTick();
        await nextTick();
        (document.querySelector('[data-action-id="add-prompt"]') as HTMLButtonElement).click();
        expect(wrapper.emitted('activate')?.[0]?.[0]).toMatchObject({ id: 'add-prompt' });
        expect(document.querySelector('button[aria-label="Back to previous quick actions"]')).toBeNull();
        wrapper.unmount();
    });

    it('switches between generic external fans while keeping only one open', async () => {
        const wrapper = await mountSuspended(QuickActionWheel, {
            attachTo: document.body,
            props: { actions: multipleFanActions, x: 500, y: 500 },
            global: { stubs: { UiIcon: true } },
        });
        const menu = document.querySelector<HTMLElement>('[role="menu"]')!;
        const addNode = document.querySelector<HTMLButtonElement>('[data-action-id="add-node"]')!;
        const presets = document.querySelector<HTMLButtonElement>('[data-action-id="presets"]')!;

        addNode.dispatchEvent(new PointerEvent('pointerenter'));
        await nextTick();
        expect(document.querySelector('[data-action-id="add-prompt"]')).not.toBeNull();

        presets.dispatchEvent(new PointerEvent('pointerenter'));
        await nextTick();
        expect(document.querySelector('[data-action-id="add-prompt"]')).toBeNull();
        const presetAction = document.querySelector<HTMLButtonElement>('[data-action-id="preset-one"]')!;
        expect(presetAction).not.toBeNull();
        expect(presetAction.getAttribute('aria-label')).toBe('Long accessible preset name');
        expect(presets.getAttribute('aria-expanded')).toBe('true');
        expect(addNode.getAttribute('aria-expanded')).toBe('false');

        presets.click();
        await nextTick();
        await nextTick();
        expect(document.activeElement).toBe(presetAction);
        menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
        await nextTick();
        expect(document.querySelectorAll('[data-external-quick-action]')).toHaveLength(0);
        expect(document.activeElement).toBe(presets);

        menu.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        expect(wrapper.emitted('close')).toHaveLength(1);
        wrapper.unmount();
    });
});
