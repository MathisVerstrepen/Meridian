import { expect, test } from '@playwright/test';
import type { Locator } from '@playwright/test';
import { QUICK_WORKFLOW_SETTINGS_KEYS } from '../fixtures/quickWorkflowWheelFixture';
import {
    closeQuickWorkflowWheel,
    expectWheelOriginAtHandle,
    expectWheelOutsideHandle,
    hoverWheelBridge,
    installBottomWheelAnimationCollector,
    mountQuickWorkflowWheelFixture,
    movePointerToQuickWorkflowHandle,
    openQuickWorkflowWheel,
    quickWorkflowHandle,
    readBottomWheelAnimation,
    readQuickWorkflowState,
    waitForQuickWorkflowNodeBounds,
    wheelAndHandleCenterX,
} from '../support/quickWorkflowWheelFixture';

const EXPECTED_AUTO_PLACEMENT_GAP = 150;

const expectGithubIconContrast = async (icon: Locator) => {
    await expect(icon).toBeVisible();
    const colors = await icon.evaluate((element) => {
        const probe = document.createElement('span');
        document.body.append(probe);

        probe.style.color = 'var(--color-github)';
        const github = getComputedStyle(probe).color;
        probe.style.color = 'var(--color-soft-silk)';
        const softSilk = getComputedStyle(probe).color;
        probe.remove();

        return { icon: getComputedStyle(element).color, github, softSilk };
    });

    expect(colors.icon).toBe(colors.softSilk);
    expect(colors.icon).not.toBe(colors.github);
};

test.beforeEach(async ({ page }) => {
    await mountQuickWorkflowWheelFixture(page);
});

test('renders six independent settings editors and bindings', async ({ page }) => {
    const editors = page.getByTestId('wheel-settings-editors');
    await expect(editors.getByText(/^(Context|Prompt|Attachment) (input|output)$/)).toHaveCount(6);

    for (const key of QUICK_WORKFLOW_SETTINGS_KEYS) {
        const before = await readQuickWorkflowState(page);
        await page.getByTestId(`mutate-${key}`).click();
        const after = await readQuickWorkflowState(page);
        expect(after.wheels[key]?.[0]).toBe(`${key}-changed`);
        for (const otherKey of QUICK_WORKFLOW_SETTINGS_KEYS.filter((candidate) => candidate !== key)) {
            expect(after.wheels[otherKey]).toEqual(before.wheels[otherKey]);
        }
    }
});

test('uses theme-aware contrast for GitHub icons on dark wheel and settings surfaces', async ({
    page,
}) => {
    const handle = quickWorkflowHandle(page, 'attachment', 'target', 'generator-anchor');
    const wheel = await openQuickWorkflowWheel(page, handle);
    await expectGithubIconContrast(wheel.locator('[data-github-icon-contrast="wheel"]'));
    await closeQuickWorkflowWheel(page);

    const settings = page.getByTestId('wheel-settings-editors');
    const summaryIcon = settings.locator(
        '[data-github-icon-contrast="settings-summary"]',
    );
    await expectGithubIconContrast(summaryIcon);
});

test('filters each handle wheel and renders outward with upright content', async ({ page }) => {
    const cases = [
        ['context', 'target', 'generator-anchor', 'top', 3],
        ['context', 'source', 'generator-anchor', 'bottom', 3],
        ['prompt', 'target', 'prompt-anchor', 'top', 1],
        ['prompt', 'source', 'prompt-anchor', 'bottom', 3],
        ['attachment', 'target', 'generator-anchor', 'left', 2],
        ['attachment', 'source', 'attachment-anchor', 'right', 3],
    ] as const;

    for (const [category, direction, nodeId, side, sectorCount] of cases) {
        const handle = quickWorkflowHandle(page, category, direction, nodeId);
        const wheel = await openQuickWorkflowWheel(page, handle);
        await expectWheelOriginAtHandle(wheel, handle, side);
        await expectWheelOutsideHandle(wheel, handle, side);
        await expect(wheel.locator('[data-wheel-slot]')).toHaveCount(sectorCount);
        await expect(wheel.locator('[data-wheel-content-upright="true"]')).toHaveCount(sectorCount);
        await closeQuickWorkflowWheel(page);
    }

    const metaHandle = quickWorkflowHandle(page, 'prompt', 'source', 'prompt-anchor');
    await page.keyboard.down('Meta');
    await movePointerToQuickWorkflowHandle(page, metaHandle);
    await expect(metaHandle.locator('[data-wheel-side="bottom"]')).toBeVisible();
    await page.keyboard.up('Meta');
    await page.mouse.move(0, 0);
});

test('keeps every sampled bottom enter frame outside the node while growing outward', async ({
    page,
}) => {
    const handle = quickWorkflowHandle(page, 'context', 'source', 'generator-anchor');
    await installBottomWheelAnimationCollector(page);
    await openQuickWorkflowWheel(page, handle);
    const samples = await readBottomWheelAnimation(page);

    expect(samples.length).toBeGreaterThan(2);
    expect(new Set(samples.map(({ wheel }) => Math.round(wheel.height))).size).toBeGreaterThan(1);
    expect(samples.at(-1)!.wheel.height).toBeGreaterThan(samples[0]!.wheel.height);
    expect(samples.at(-1)!.wheel.bottom).toBeGreaterThan(samples[0]!.wheel.bottom);
    for (const sample of samples) {
        expect(sample.wheel.top).toBeGreaterThanOrEqual(sample.node.bottom - 2);
    }

    await closeQuickWorkflowWheel(page);
});

test('centers split top wheels on their production prompt and context handle offsets', async ({
    page,
}) => {
    const promptHandle = quickWorkflowHandle(page, 'prompt', 'target', 'generator-anchor');
    const promptWheel = await openQuickWorkflowWheel(page, promptHandle);
    const promptCenters = await wheelAndHandleCenterX(promptWheel, promptHandle);
    await closeQuickWorkflowWheel(page);

    const contextHandle = quickWorkflowHandle(page, 'context', 'target', 'generator-anchor');
    const contextWheel = await openQuickWorkflowWheel(page, contextHandle);
    const contextCenters = await wheelAndHandleCenterX(contextWheel, contextHandle);
    await closeQuickWorkflowWheel(page);

    expect(promptCenters).not.toBeNull();
    expect(contextCenters).not.toBeNull();
    expect(Math.abs(promptCenters!.wheel - promptCenters!.handle)).toBeLessThanOrEqual(2);
    expect(Math.abs(contextCenters!.wheel - contextCenters!.handle)).toBeLessThanOrEqual(2);
    expect(Math.abs(contextCenters!.wheel - promptCenters!.wheel)).toBeGreaterThan(20);
});

test('keeps the wheel active across real pointer travel through the radial bridge', async ({
    page,
}) => {
    const handle = quickWorkflowHandle(page, 'context', 'source', 'generator-anchor');
    const wheel = await openQuickWorkflowWheel(page, handle);
    await hoverWheelBridge(page, wheel);
    await expect(wheel).toBeVisible();

    const sector = wheel.locator('[data-wheel-slot="Slot 1"]');
    await sector.hover();
    await expect(wheel).toBeVisible();
    await sector.click();
    await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBeGreaterThan(3);
    await closeQuickWorkflowWheel(page);
});

test('creates prompt and attachment workflows in both directions with exact handles', async ({
    page,
}) => {
    const cases = [
        {
            category: 'prompt',
            direction: 'target',
            anchorId: 'prompt-anchor',
            mainType: 'prompt',
        },
        {
            category: 'prompt',
            direction: 'source',
            anchorId: 'prompt-anchor',
            mainType: 'textToText',
        },
        {
            category: 'attachment',
            direction: 'target',
            anchorId: 'generator-anchor',
            mainType: 'filePrompt',
        },
        {
            category: 'attachment',
            direction: 'source',
            anchorId: 'attachment-anchor',
            mainType: 'textToText',
        },
    ] as const;

    for (const testCase of cases) {
        await page.getByTestId('reset-graph').click();
        await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBe(3);
        const before = await readQuickWorkflowState(page);
        const handle = quickWorkflowHandle(
            page,
            testCase.category,
            testCase.direction,
            testCase.anchorId,
        );
        const wheel = await openQuickWorkflowWheel(page, handle);
        await wheel.locator('[data-wheel-slot="Slot 1"]').click();
        await closeQuickWorkflowWheel(page);

        await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBeGreaterThan(3);
        const state = await readQuickWorkflowState(page);
        const originalIds = new Set(before.nodes.map((node) => node.id));
        const main = state.nodes.find(
            (node) => !originalIds.has(node.id) && node.type === testCase.mainType,
        );
        const anchor = state.nodes.find((node) => node.id === testCase.anchorId);
        expect(main).toBeDefined();
        expect(anchor).toBeDefined();
        const renderedMain = await waitForQuickWorkflowNodeBounds(page, main!.id);
        const renderedAnchor = await waitForQuickWorkflowNodeBounds(page, anchor!.id);

        const upstream = testCase.direction === 'target';
        if (testCase.category === 'attachment') {
            expect(
                upstream
                    ? main!.position.x < anchor!.position.x
                    : main!.position.x > anchor!.position.x,
            ).toBe(true);
            expect(main!.position.y).toBe(anchor!.position.y);
            expect(
                upstream
                    ? renderedAnchor.position.x -
                          (renderedMain.position.x + renderedMain.dimensions.width)
                    : renderedMain.position.x -
                          (renderedAnchor.position.x + renderedAnchor.dimensions.width),
            ).toBe(EXPECTED_AUTO_PLACEMENT_GAP);
        } else {
            expect(
                upstream
                    ? main!.position.y < anchor!.position.y
                    : main!.position.y > anchor!.position.y,
            ).toBe(true);
            expect(
                upstream
                    ? renderedAnchor.position.y -
                          (renderedMain.position.y + renderedMain.dimensions.height)
                    : renderedMain.position.y -
                          (renderedAnchor.position.y + renderedAnchor.dimensions.height),
            ).toBe(EXPECTED_AUTO_PLACEMENT_GAP);
        }
        expect(state.edges).toContainEqual({
            source: upstream ? main!.id : anchor!.id,
            target: upstream ? anchor!.id : main!.id,
            sourceHandle: `${testCase.category}_${upstream ? main!.id : anchor!.id}`,
            targetHandle: `${testCase.category}_${upstream ? anchor!.id : main!.id}`,
        });
    }
});

test('resolves attachment placement collisions downward on both horizontal sides', async ({
    page,
}) => {
    const cases = [
        {
            direction: 'target',
            anchorId: 'generator-anchor',
            mainType: 'filePrompt',
            slot: 'Slot 1',
        },
        {
            direction: 'source',
            anchorId: 'attachment-anchor',
            mainType: 'parallelization',
            slot: 'Slot 3',
        },
    ] as const;

    for (const testCase of cases) {
        await page.getByTestId('reset-graph').click();
        await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBe(3);
        await expect(page.locator('.vue-flow__node[data-id="prompt-anchor"]')).toBeVisible();

        await page.getByTestId(`force-attachment-${testCase.direction}-collision`).click();
        const before = await readQuickWorkflowState(page);
        const blocker = before.nodes.find((node) => node.id === 'prompt-anchor');
        const anchor = before.nodes.find((node) => node.id === testCase.anchorId);
        expect(blocker).toBeDefined();
        expect(anchor).toBeDefined();
        expect(blocker!.position.y).toBe(anchor!.position.y);

        const handle = quickWorkflowHandle(
            page,
            'attachment',
            testCase.direction,
            testCase.anchorId,
        );
        const wheel = await openQuickWorkflowWheel(page, handle);
        await wheel.locator(`[data-wheel-slot="${testCase.slot}"]`).click();
        await closeQuickWorkflowWheel(page);

        const originalIds = new Set(before.nodes.map((node) => node.id));
        await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBeGreaterThan(3);

        const state = await readQuickWorkflowState(page);
        const createdNodes = state.nodes.filter((node) => !originalIds.has(node.id));
        const main = createdNodes.find(
            (node) => !originalIds.has(node.id) && node.type === testCase.mainType,
        );
        expect(main).toBeDefined();
        const renderedBlocker = await waitForQuickWorkflowNodeBounds(page, blocker!.id);
        await Promise.all(
            createdNodes.map((node) => waitForQuickWorkflowNodeBounds(page, node.id)),
        );
        await expect
            .poll(async () => {
                const currentCreatedNodes = (await readQuickWorkflowState(page)).nodes.filter(
                    (node) => !originalIds.has(node.id),
                );
                return (
                    Math.min(...currentCreatedNodes.map((node) => node.position.y)) -
                    (renderedBlocker.position.y + renderedBlocker.dimensions.height)
                );
            })
            .toBe(EXPECTED_AUTO_PLACEMENT_GAP);
        const renderedMain = await waitForQuickWorkflowNodeBounds(page, main!.id);
        expect(renderedMain.position.x).toBe(blocker!.position.x);
        expect(
            testCase.direction === 'target'
                ? main!.position.x < anchor!.position.x
                : main!.position.x > anchor!.position.x,
        ).toBe(true);

        const upstream = testCase.direction === 'target';
        expect(state.edges).toContainEqual({
            source: upstream ? main!.id : anchor!.id,
            target: upstream ? anchor!.id : main!.id,
            sourceHandle: `attachment_${upstream ? main!.id : anchor!.id}`,
            targetHandle: `attachment_${upstream ? anchor!.id : main!.id}`,
        });
    }
});

test('resolves target collisions right by one group bound gap and moves linked nodes equally', async ({
    page,
}) => {
    await page.getByTestId('reset-graph').click();
    await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBe(3);
    await page.getByTestId('force-default-target-collision').click();

    const before = await readQuickWorkflowState(page);
    const originalIds = new Set(before.nodes.map((node) => node.id));
    const anchor = await waitForQuickWorkflowNodeBounds(page, 'generator-anchor');
    const blocker = await waitForQuickWorkflowNodeBounds(page, 'prompt-anchor');
    const initialMainPosition = {
        x: anchor.position.x,
        y: anchor.position.y - 300 - EXPECTED_AUTO_PLACEMENT_GAP,
    };
    const initialLinkedPosition = {
        x: initialMainPosition.x - 200,
        y: initialMainPosition.y - 300,
    };

    const handle = quickWorkflowHandle(page, 'context', 'target', 'generator-anchor');
    const wheel = await openQuickWorkflowWheel(page, handle);
    await wheel.locator('[data-wheel-slot="Slot 1"]').click();
    await closeQuickWorkflowWheel(page);

    await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBe(5);
    const created = (await readQuickWorkflowState(page)).nodes.filter(
        (node) => !originalIds.has(node.id),
    );
    const main = created.find((node) => node.type === 'textToText');
    const linked = created.find((node) => node.type === 'prompt');
    expect(main).toBeDefined();
    expect(linked).toBeDefined();

    await expect
        .poll(async () => {
            const currentMain = await waitForQuickWorkflowNodeBounds(page, main!.id);
            const currentLinked = await waitForQuickWorkflowNodeBounds(page, linked!.id);
            return (
                Math.min(currentMain.position.x, currentLinked.position.x) -
                (blocker.position.x + blocker.dimensions.width)
            );
        })
        .toBe(EXPECTED_AUTO_PLACEMENT_GAP);

    const renderedMain = await waitForQuickWorkflowNodeBounds(page, main!.id);
    const renderedLinked = await waitForQuickWorkflowNodeBounds(page, linked!.id);
    const mainDelta = {
        x: renderedMain.position.x - initialMainPosition.x,
        y: renderedMain.position.y - initialMainPosition.y,
    };
    const linkedDelta = {
        x: renderedLinked.position.x - initialLinkedPosition.x,
        y: renderedLinked.position.y - initialLinkedPosition.y,
    };
    expect(mainDelta).toEqual(linkedDelta);
    expect(mainDelta.x).toBeGreaterThan(0);
});

test('creates a context workflow downstream with exact handles and linked prompt', async ({ page }) => {
    const before = await readQuickWorkflowState(page);
    const originalIds = new Set(before.nodes.map((node) => node.id));
    const anchor = await waitForQuickWorkflowNodeBounds(page, 'generator-anchor');
    const initialMainPosition = {
        x: anchor.position.x,
        y: anchor.position.y + anchor.dimensions.height + EXPECTED_AUTO_PLACEMENT_GAP,
    };
    const initialLinkedPosition = {
        x: initialMainPosition.x - 200,
        y: initialMainPosition.y - 300,
    };
    const handle = quickWorkflowHandle(page, 'context', 'source', 'generator-anchor');
    const wheel = await openQuickWorkflowWheel(page, handle);
    await wheel.locator('[data-wheel-slot="Slot 1"]').click();
    await closeQuickWorkflowWheel(page);

    await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBe(5);
    const state = await readQuickWorkflowState(page);
    const main = state.nodes.find(
        (node) => !originalIds.has(node.id) && node.type === 'textToText',
    );
    const linkedPrompt = state.nodes.find(
        (node) => !originalIds.has(node.id) && node.type === 'prompt',
    );
    expect(main).toBeDefined();
    expect(linkedPrompt).toBeDefined();

    await expect
        .poll(async () => {
            const currentMain = await waitForQuickWorkflowNodeBounds(page, main!.id);
            const currentLinked = await waitForQuickWorkflowNodeBounds(page, linkedPrompt!.id);
            return (
                Math.min(currentMain.position.y, currentLinked.position.y) -
                (anchor.position.y + anchor.dimensions.height)
            );
        })
        .toBe(EXPECTED_AUTO_PLACEMENT_GAP);

    const renderedMain = await waitForQuickWorkflowNodeBounds(page, main!.id);
    const renderedLinked = await waitForQuickWorkflowNodeBounds(page, linkedPrompt!.id);
    expect(renderedMain.position.x).toBe(initialMainPosition.x);
    expect(renderedLinked.position.x).toBe(initialLinkedPosition.x);
    const mainDelta = renderedMain.position.y - initialMainPosition.y;
    const linkedDelta = renderedLinked.position.y - initialLinkedPosition.y;
    expect(mainDelta).toBe(linkedDelta);
    expect(mainDelta).toBeGreaterThan(0);

    for (const member of [renderedMain, renderedLinked]) {
        const intersectsAnchor =
            member.position.x < anchor.position.x + anchor.dimensions.width &&
            member.position.x + member.dimensions.width > anchor.position.x &&
            member.position.y < anchor.position.y + anchor.dimensions.height &&
            member.position.y + member.dimensions.height > anchor.position.y;
        expect(intersectsAnchor).toBe(false);
    }
    expect(state.edges).toContainEqual({
        source: 'generator-anchor',
        target: main!.id,
        sourceHandle: 'context_generator-anchor',
        targetHandle: `context_${main!.id}`,
    });
    expect(state.edges).toContainEqual({
        source: linkedPrompt!.id,
        target: main!.id,
        sourceHandle: `prompt_${linkedPrompt!.id}`,
        targetHandle: `prompt_${main!.id}`,
    });
});

test('creates a context workflow upstream into the exact hovered target', async ({ page }) => {
    const handle = quickWorkflowHandle(page, 'context', 'target', 'generator-anchor');
    const wheel = await openQuickWorkflowWheel(page, handle);
    await wheel.locator('[data-wheel-slot="Slot 1"]').click();
    await closeQuickWorkflowWheel(page);

    await expect.poll(async () => (await readQuickWorkflowState(page)).nodes.length).toBe(5);
    const state = await readQuickWorkflowState(page);
    const main = state.nodes.find(
        (node) => node.type === 'textToText' && node.id !== 'generator-anchor',
    );
    expect(main).toBeDefined();
    expect(main!.position.y).toBeLessThan(
        state.nodes.find((node) => node.id === 'generator-anchor')!.position.y,
    );
    expect(state.edges).toContainEqual({
        source: main!.id,
        target: 'generator-anchor',
        sourceHandle: `context_${main!.id}`,
        targetHandle: 'context_generator-anchor',
    });
});

test('rejects occupied single-input targets and stale incompatible presets before mutation', async ({
    page,
}) => {
    const initial = await readQuickWorkflowState(page);
    await page.getByTestId('run-stale-preset').click();
    expect((await readQuickWorkflowState(page)).nodes).toEqual(initial.nodes);
    expect((await readQuickWorkflowState(page)).edges).toEqual(initial.edges);

    await page.getByTestId('run-occupied-prompt').click();
    const occupied = await readQuickWorkflowState(page);
    expect(occupied.nodes).toEqual(initial.nodes);
    expect(occupied.edges).toHaveLength(1);

    const handle = quickWorkflowHandle(page, 'prompt', 'target', 'prompt-anchor');
    await page.keyboard.down('Control');
    await handle.dispatchEvent('mouseenter');
    await expect(handle.locator('[data-wheel-side]')).toHaveCount(0);
    await closeQuickWorkflowWheel(page);
});
