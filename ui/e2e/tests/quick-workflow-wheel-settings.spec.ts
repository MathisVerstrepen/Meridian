import type { Locator, Page } from '@playwright/test';
import {
    constrainQuickWorkflowSettings,
    mountQuickWorkflowWheelFixture,
    readQuickWorkflowState,
    seedInvalidQuickWorkflowSettings,
    seedLegacyQuickWorkflowLengths,
    setQuickWorkflowSettingsTheme,
    expect,
    test,
} from '../support/quickWorkflowWheelFixture';

const matrix = (page: Page) => page.getByRole('tablist', { name: 'Quick workflow wheels' });
const selectWheel = async (page: Page, name: RegExp) => {
    const tab = matrix(page).getByRole('tab', { name });
    await tab.click();
    await expect(tab).toHaveAttribute('aria-selected', 'true');
    return tab;
};
const activeWheelPanel = async (page: Page) => {
    const tab = matrix(page).getByRole('tab', { selected: true });
    const panelId = await tab.getAttribute('aria-controls');
    if (!panelId) throw new Error('Selected wheel tab does not control a panel');
    return page.locator(`#${panelId}`);
};

const readSurfaceStyle = (locator: Locator) =>
    locator.evaluate((element) => {
        const style = getComputedStyle(element);
        const alpha = Number((style.backgroundColor.match(/[\d.]+/g) ?? [0, 0, 0, 0])[3] ?? 1);
        return {
            backgroundAlpha: alpha,
            borderRadius: [
                style.borderTopLeftRadius,
                style.borderTopRightRadius,
                style.borderBottomRightRadius,
                style.borderBottomLeftRadius,
            ].map(Number.parseFloat),
            borderWidths: [
                style.borderTopWidth,
                style.borderRightWidth,
                style.borderBottomWidth,
                style.borderLeftWidth,
            ].map(Number.parseFloat),
        };
    });

const expectFlatComposition = async (page: Page, divider: 'right' | 'bottom') => {
    const selector = page.locator('section[aria-label="Wheel selector"]');
    const activePanel = await activeWheelPanel(page);
    const slotPanel = activePanel.getByRole('tabpanel');
    const surfaces = [selector, activePanel, slotPanel];

    for (const surface of surfaces) {
        const style = await readSurfaceStyle(surface);
        expect(style.backgroundAlpha).toBe(0);
        expect(style.borderRadius.every((radius) => radius === 0)).toBe(true);
        if (surface !== selector) expect(style.borderWidths.every((width) => width === 0)).toBe(true);
    }

    const selectorBorders = (await readSurfaceStyle(selector)).borderWidths;
    expect(selectorBorders.filter((width) => width > 0)).toHaveLength(1);
    expect(selectorBorders[divider === 'right' ? 1 : 2]).toBeGreaterThan(0);

    for (const tabs of [matrix(page).getByRole('tab'), activePanel.getByRole('tablist').getByRole('tab')]) {
        const styles = await tabs.evaluateAll((elements) =>
            elements.map((element) => {
                const style = getComputedStyle(element);
                return {
                    radius: Number.parseFloat(style.borderTopLeftRadius),
                    borderedSides: [
                        style.borderTopWidth,
                        style.borderRightWidth,
                        style.borderBottomWidth,
                        style.borderLeftWidth,
                    ].filter((width) => Number.parseFloat(width) > 0).length,
                };
            }),
        );
        expect(styles.every(({ radius, borderedSides }) => radius === 0 && borderedSides < 4)).toBe(true);
    }
};

test.beforeEach(async ({ page }) => {
    await mountQuickWorkflowWheelFixture(page);
});

test('renders six matrix tabs, one active editor, and Context output by default', async ({ page }) => {
    const tabs = matrix(page).getByRole('tab');
    await expect(tabs).toHaveCount(6);
    const selected = matrix(page).getByRole('tab', { selected: true });
    await expect(selected).toHaveAccessibleName(/Context Output.*after.*3 configured.*0 need repair/i);
    await expect(selected).toHaveAttribute('tabindex', '0');
    await expect(page.getByRole('tabpanel')).toHaveCount(2);
    const panel = await activeWheelPanel(page);
    await expect(panel).toHaveAttribute('aria-labelledby', await selected.getAttribute('id'));
    await expect(panel.getByRole('tabpanel')).toHaveCount(1);
    await expect(panel.getByLabel('Output flow: Current node creates before Preset')).toContainText('Current node');
    await selectWheel(page, /Context Input/i);
    await expect((await activeWheelPanel(page)).getByLabel('Input flow: Preset creates before Current node')).toContainText(
        '[Preset]',
    );
});

test('uses canonical handle colors for visible category markers and the selected rail', async ({ page }) => {
    const markers = matrix(page).locator('[data-wheel-category-marker]');
    await expect(markers).toHaveCount(6);
    for (const marker of await markers.all()) await expect(marker).toBeVisible();

    const categories = [
        ['Context', '--color-node-cat-context'],
        ['Prompt', '--color-node-cat-prompt'],
        ['Attachment', '--color-node-cat-attachment'],
    ] as const;
    for (const [category, cssVariable] of categories) {
        const tab = await selectWheel(page, new RegExp(`${category} Output`, 'i'));
        await expect(tab.getByText(`${category} Output`, { exact: true })).toBeVisible();
        const colors = await tab.evaluate((element, variable) => {
            const marker = element.querySelector<HTMLElement>('[data-wheel-category-marker]');
            const rail = element.querySelector<HTMLElement>('[data-wheel-selected-rail]');
            if (!marker || !rail) throw new Error('Selected wheel category cue is missing');
            const probe = document.createElement('span');
            probe.style.color = `var(${variable})`;
            element.append(probe);
            const canonical = getComputedStyle(probe).color;
            probe.remove();
            return {
                canonical,
                marker: getComputedStyle(marker).backgroundColor,
                rail: getComputedStyle(rail).backgroundColor,
            };
        }, cssVariable);
        expect(colors.marker).toBe(colors.canonical);
        expect(colors.rail).toBe(colors.canonical);
    }
});

test('keeps selector, editor, slot detail, and tabs flat at desktop and 390px', async ({ page }) => {
    await expectFlatComposition(page, 'right');
    await constrainQuickWorkflowSettings(page);
    await expectFlatComposition(page, 'bottom');
});

test('derives the exact ordered main and linked choices for every wheel', async ({ page }) => {
    const cases = [
        [/Context Input/i, ['Text to Text', 'Routing', 'Parallelization'], ['Prompt', 'Attachment', 'GitHub']],
        [/Context Output/i, ['Text to Text', 'Routing', 'Parallelization'], ['Prompt', 'Attachment', 'GitHub']],
        [/Prompt Input/i, ['Prompt'], []],
        [/Prompt Output/i, ['Text to Text', 'Routing', 'Parallelization'], ['Attachment', 'GitHub']],
        [/Attachment Input/i, ['Attachment', 'GitHub'], []],
        [/Attachment Output/i, ['Text to Text', 'Routing', 'Parallelization'], ['Prompt', 'Attachment', 'GitHub']],
    ] as const;

    for (const [wheel, mains, linked] of cases) {
        await selectWheel(page, wheel);
        const panel = await activeWheelPanel(page);
        const mainGroup = panel.getByRole('group', { name: 'Main block' });
        await expect(mainGroup.getByRole('radio')).toHaveCount(mains.length);
        for (const [index, name] of mains.entries()) {
            await expect(mainGroup.getByRole('radio').nth(index)).toHaveAccessibleName(`${name} main block`);
        }
        if (!linked.length) {
            await expect(panel.getByRole('group', { name: 'Linked blocks' })).toHaveCount(0);
            await expect(panel.getByRole('checkbox')).toHaveCount(0);
        } else {
            const linkedGroup = panel.getByRole('group', { name: 'Linked blocks' });
            await expect(linkedGroup.getByRole('checkbox')).toHaveCount(linked.length);
            for (const [index, name] of linked.entries()) {
                await expect(linkedGroup.getByRole('checkbox').nth(index)).toHaveAccessibleName(`${name} linked block`);
            }
        }
    }
});

test('keeps native choice inputs accessible with immediate, distinct card feedback', async ({ page }) => {
    const panel = await activeWheelPanel(page);
    const controls = panel.locator('input[type="radio"], input[type="checkbox"]');
    const footprints = await controls.evaluateAll((elements) =>
        elements.map((element) => {
            const bounds = element.getBoundingClientRect();
            return {
                height: bounds.height,
                position: getComputedStyle(element).position,
                width: bounds.width,
            };
        }),
    );
    expect(footprints.length).toBeGreaterThan(0);
    expect(
        footprints.every(({ height, position, width }) => height <= 1 && width <= 1 && position === 'absolute'),
    ).toBe(true);

    const routing = panel.getByRole('radio', { name: 'Routing main block' });
    const routingCard = routing.locator('..');
    const readFeedback = () =>
        routingCard.evaluate((element) => {
            const style = getComputedStyle(element);
            return {
                background: style.backgroundColor,
                border: style.borderColor,
                transitionDuration: style.transitionDuration,
            };
        });
    const finishFeedback = () =>
        routingCard.evaluate((element) => Promise.all(element.getAnimations().map((animation) => animation.finished)));

    await routing.focus();
    await expect(routing).toBeFocused();
    expect(await routingCard.evaluate((element) => getComputedStyle(element).boxShadow)).not.toBe('none');

    const idle = await readFeedback();
    const durations = idle.transitionDuration.split(',').map((duration) => Number.parseFloat(duration));
    expect(durations.every((duration) => duration >= 0.075 && duration <= 0.1)).toBe(true);
    await routingCard.hover();
    await finishFeedback();
    const uncheckedHover = await readFeedback();
    expect(uncheckedHover.background).not.toBe(idle.background);
    expect(uncheckedHover.border).not.toBe(idle.border);

    await routingCard.click();
    await expect(routing).toBeChecked();
    await finishFeedback();
    const selectedHover = await readFeedback();
    await panel.getByRole('radio', { name: 'Text to Text main block' }).locator('..').hover();
    await finishFeedback();
    const selected = await readFeedback();
    expect(selected.background).not.toBe(idle.background);
    expect(selected.border).not.toBe(idle.border);
    expect(selectedHover.background).not.toBe(selected.background);
    expect(selectedHover.background).not.toBe(uncheckedHover.background);
    expect(selectedHover.border).not.toBe(uncheckedHover.border);

    const github = panel.getByRole('checkbox', { name: 'GitHub linked block' });
    await expect(github).not.toBeChecked();
    await github.locator('..').click();
    await expect(github).toBeChecked();
});

test('disables linked choices until the slot has an allowed main block without changing persisted options', async ({
    page,
}) => {
    let panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 4.*Empty/i }).click();
    await expect(panel.getByText('Select a main block first', { exact: true })).toBeVisible();
    await expect(panel.getByRole('checkbox')).toHaveCount(3);
    for (const checkbox of await panel.getByRole('checkbox').all()) await expect(checkbox).toBeDisabled();

    await panel.getByRole('radio', { name: 'Routing main block' }).check();
    for (const checkbox of await panel.getByRole('checkbox').all()) await expect(checkbox).toBeEnabled();

    await seedInvalidQuickWorkflowSettings(page);
    const seeded = await readQuickWorkflowState(page);
    panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 4.*needs repair/i }).click();
    await expect(panel.getByText('Select a valid main block first', { exact: true })).toBeVisible();
    for (const checkbox of await panel.getByRole('checkbox').all()) await expect(checkbox).toBeDisabled();
    expect((await readQuickWorkflowState(page)).wheels.contextWheel?.[3]).toEqual(
        seeded.wheels.contextWheel?.[3],
    );
});

test('supports two-dimensional matrix roving focus and linked tab semantics', async ({ page }) => {
    const selected = matrix(page).getByRole('tab', { selected: true });
    await selected.focus();
    await page.keyboard.press('ArrowRight');
    await expect(matrix(page).getByRole('tab', { name: /Context Input/i })).toBeFocused();
    await page.keyboard.press('ArrowUp');
    await expect(matrix(page).getByRole('tab', { name: /Attachment Input/i })).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(matrix(page).getByRole('tab', { name: /Context Input/i })).toBeFocused();
    await page.keyboard.press('End');
    await expect(matrix(page).getByRole('tab', { name: /Attachment Output/i })).toBeFocused();
    await page.keyboard.press('Home');
    const contextInput = matrix(page).getByRole('tab', { name: /Context Input/i });
    await expect(contextInput).toBeFocused();
    const panel = await activeWheelPanel(page);
    await expect(panel).toHaveAttribute('aria-labelledby', await contextInput.getAttribute('id'));
});

test('supports four fixed roving slot tabs controlling one stable panel', async ({ page }) => {
    const panel = await activeWheelPanel(page);
    const slotList = panel.getByRole('tablist', { name: /Context Output slots/i });
    const slots = slotList.getByRole('tab');
    await expect(slots).toHaveCount(4);
    for (let index = 0; index < 4; index += 1) {
        await expect(slots.nth(index)).toHaveAccessibleName(new RegExp(`Slot ${index + 1}`));
    }
    const controlledIds = await slots.evaluateAll((elements) => elements.map((element) => element.getAttribute('aria-controls')));
    expect(new Set(controlledIds).size).toBe(1);
    await slots.first().focus();
    await page.keyboard.press('ArrowLeft');
    await expect(slots.nth(3)).toBeFocused();
    await page.keyboard.press('Home');
    await expect(slots.first()).toBeFocused();
    await page.keyboard.press('End');
    await expect(slots.nth(3)).toBeFocused();
    await page.keyboard.press('ArrowRight');
    await expect(slots.first()).toBeFocused();
    await expect(panel.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', await slots.first().getAttribute('id'));
});

test('makes controlled independent edits and marks global settings dirty', async ({ page }) => {
    const before = await readQuickWorkflowState(page);
    let panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 4/ }).click();
    await panel.getByRole('radio', { name: 'Routing main block' }).check();
    await panel.getByRole('checkbox', { name: 'GitHub linked block' }).check();

    await selectWheel(page, /Prompt Output/i);
    panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 4/ }).click();
    await panel.getByRole('radio', { name: 'Parallelization main block' }).check();
    const after = await readQuickWorkflowState(page);
    expect(after.hasChanged).toBe(true);
    expect(after.wheels.contextWheel?.[3]).toEqual({ name: 'Slot 4', mainBloc: 'routing', options: ['github'] });
    expect(after.wheels.promptOutputWheel?.[3]).toEqual({ name: 'Slot 4', mainBloc: 'parallelization', options: [] });
    for (const key of Object.keys(before.wheels).filter((key) => !['contextWheel', 'promptOutputWheel'].includes(key))) {
        expect(after.wheels[key]).toEqual(before.wheels[key]);
    }
    expect(after.wheels.contextWheel?.slice(0, 3)).toEqual(before.wheels.contextWheel?.slice(0, 3));
});

test('does not normalize invalid data until explicit Clear or Repair', async ({ page }) => {
    await seedInvalidQuickWorkflowSettings(page);
    const seeded = await readQuickWorkflowState(page);
    let panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 3.*needs repair/i }).click();
    await selectWheel(page, /Prompt Output/i);
    await selectWheel(page, /Context Output/i);
    expect((await readQuickWorkflowState(page)).wheels).toEqual(seeded.wheels);

    panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 3.*needs repair/i }).click();
    const repairLinked = panel.getByRole('button', { name: 'Repair Slot 3' });
    await repairLinked.click();
    await expect(panel.getByRole('button', { name: 'Clear Slot 3' })).toBeFocused();
    expect((await readQuickWorkflowState(page)).wheels.contextWheel?.[2]).toEqual({
        name: 'Slot 3',
        mainBloc: 'routing',
        options: ['prompt'],
    });

    await panel.getByRole('tab', { name: /Slot 4.*needs repair/i }).click();
    await panel.getByRole('button', { name: 'Repair Slot 4' }).click();
    await expect(panel.getByRole('heading', { name: 'Configure Slot 4' })).toBeFocused();
    expect((await readQuickWorkflowState(page)).wheels.contextWheel?.[3]).toEqual({
        name: 'Slot 4',
        mainBloc: null,
        options: [],
    });
});

test('Clear preserves the slot name, updates counts, and announces the action', async ({ page }) => {
    const before = await readQuickWorkflowState(page);
    const panel = await activeWheelPanel(page);
    await panel.getByRole('button', { name: 'Clear Slot 1' }).click();
    await expect(page.getByText('Slot 1 cleared.', { exact: true })).toBeAttached();
    const after = await readQuickWorkflowState(page);
    expect(after.wheels.contextWheel?.[0]).toEqual({ name: 'Slot 1', mainBloc: null, options: [] });
    expect(after.wheels.contextWheel?.slice(1)).toEqual(before.wheels.contextWheel?.slice(1));
    await expect(matrix(page).getByRole('tab', { selected: true })).toHaveAccessibleName(/2 configured/);
    await expect(panel.getByRole('button', { name: 'Clear Slot 1' })).toBeDisabled();
    await expect(panel.getByRole('tab', { name: /Slot 1.*Empty/i })).toBeFocused();
});

test('preserves short and long legacy arrays and only fills explicitly edited missing positions', async ({ page }) => {
    await seedLegacyQuickWorkflowLengths(page);
    const seeded = await readQuickWorkflowState(page);
    expect(seeded.wheels.contextInputWheel).toHaveLength(2);
    expect(seeded.wheels.attachmentOutputWheel).toHaveLength(5);

    await selectWheel(page, /Context Input/i);
    let panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 4.*Empty/i }).click();
    await panel.getByRole('radio', { name: 'Text to Text main block' }).check();
    let state = await readQuickWorkflowState(page);
    expect(state.wheels.contextInputWheel).toHaveLength(4);
    expect(state.wheels.contextInputWheel?.[2]).toEqual({ name: 'Slot 3', mainBloc: null, options: [] });

    await selectWheel(page, /Attachment Output/i);
    panel = await activeWheelPanel(page);
    await panel.getByRole('tab', { name: /Slot 1/ }).click();
    await panel.getByRole('checkbox', { name: 'GitHub linked block' }).check();
    state = await readQuickWorkflowState(page);
    expect(state.wheels.attachmentOutputWheel).toHaveLength(5);
    expect(state.wheels.attachmentOutputWheel?.[4]).toEqual(seeded.wheels.attachmentOutputWheel?.[4]);
});

test('contains the workbench at 390px without horizontal overflow', async ({ page }) => {
    await constrainQuickWorkflowSettings(page);
    const root = page.getByTestId('quick-workflow-workbench');
    const geometry = await root.evaluate((element) => {
        const bounds = element.getBoundingClientRect();
        return {
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
            childOverflow: [...element.querySelectorAll<HTMLElement>('[role="tabpanel"]')].some(
                (child) => child.getBoundingClientRect().right > bounds.right + 1,
            ),
        };
    });
    expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth);
    expect(geometry.childOverflow).toBe(false);
});

const parseRgb = (value: string) => (value.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
const luminance = ([red = 0, green = 0, blue = 0]: number[]) => {
    const channels = [red, green, blue].map((channel) => {
        const value = channel / 255;
        return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!;
};
const contrast = (foreground: string, background: string) => {
    const lighter = Math.max(luminance(parseRgb(foreground)), luminance(parseRgb(background)));
    const darker = Math.min(luminance(parseRgb(foreground)), luminance(parseRgb(background)));
    return (lighter + 0.05) / (darker + 0.05);
};

const effectiveBackground = (icon: Locator, closestSurface: string) =>
    icon.evaluate((element, surfaceSelector) => {
        type Color = [number, number, number, number];
        const parseColor = (value: string): Color => {
            const channels = (value.match(/[\d.]+/g) ?? []).map(Number);
            return [channels[0] ?? 0, channels[1] ?? 0, channels[2] ?? 0, channels[3] ?? 1];
        };
        const composite = (foreground: Color, background: Color): Color => {
            const alpha = foreground[3] + background[3] * (1 - foreground[3]);
            if (alpha === 0) return [0, 0, 0, 0];
            return [
                (foreground[0] * foreground[3] + background[0] * background[3] * (1 - foreground[3])) / alpha,
                (foreground[1] * foreground[3] + background[1] * background[3] * (1 - foreground[3])) / alpha,
                (foreground[2] * foreground[3] + background[2] * background[3] * (1 - foreground[3])) / alpha,
                alpha,
            ];
        };

        const surface = element.closest(surfaceSelector);
        const fixtureRoot = element.closest('[data-testid="quick-workflow-fixture-page"]');
        if (!surface || !fixtureRoot) throw new Error(`Unable to resolve ${surfaceSelector} background surface`);
        const layers: Color[] = [];
        let current: Element | null = surface;
        while (current) {
            layers.push(parseColor(getComputedStyle(current).backgroundColor));
            if (current === fixtureRoot) break;
            current = current.parentElement;
        }
        if (current !== fixtureRoot) throw new Error('Background surface is outside the fixture root');
        const result = layers.reverse().reduce<Color>((background, foreground) => composite(foreground, background), [
            255,
            255,
            255,
            1,
        ]);
        return `rgb(${result[0]} ${result[1]} ${result[2]})`;
    }, closestSurface);

test('uses AA semantic GitHub choice and configured-summary icon contrast in Standard and Light themes', async ({
    page,
}) => {
    await selectWheel(page, /Attachment Input/i);
    for (const theme of ['standard', 'light'] as const) {
        await setQuickWorkflowSettingsTheme(page, theme);
        const panel = await activeWheelPanel(page);
        const markers = [
            ['settings-choice', 'label'],
            ['settings-summary', 'button'],
        ] as const;
        for (const [marker, surface] of markers) {
            const icon = panel.locator(`[data-github-icon-contrast="${marker}"]`).first();
            await expect(icon).toBeVisible();
            await expect(icon).toHaveAttribute('aria-hidden', 'true');
            const foreground = await icon.evaluate((element) => getComputedStyle(element).color);
            const background = await effectiveBackground(icon, surface);
            expect(contrast(foreground, background)).toBeGreaterThanOrEqual(4.5);
        }
    }
});

test('removes decorative motion while preserving state changes for reduced-motion users', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.reload();
    await mountQuickWorkflowWheelFixture(page);
    const control = matrix(page).getByRole('tab').first();
    expect(await control.evaluate((element) => getComputedStyle(element).transitionDuration)).toMatch(/^(0s)(, 0s)*$/);
    await control.click();
    await expect(control).toHaveAttribute('aria-selected', 'true');
});
