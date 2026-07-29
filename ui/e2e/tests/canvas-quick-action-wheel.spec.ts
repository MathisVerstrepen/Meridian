import {
    expect,
    mountCanvasQuickActionFixture,
    readCanvasQuickActionState,
    test,
} from '../support/canvasQuickActionWheelFixture';

test.beforeEach(async ({ page }) => {
    await mountCanvasQuickActionFixture(page);
});

test('@smoke opens target-aware wheels and dispatches an add action', async ({ page }) => {
    const graph = page.getByTestId('canvas-quick-action-graph');
    const graphBox = await graph.boundingBox();
    expect(graphBox).not.toBeNull();
    if (!graphBox) return;

    await page.mouse.click(graphBox.x + graphBox.width - 20, graphBox.y + graphBox.height - 20, {
        button: 'right',
    });
    const addNodeAction = page.locator('[data-action-id="add-node"]');
    await expect(addNodeAction).toBeVisible();
    const rootSegments = page.locator('[data-root-quick-action-segment]');
    expect(await rootSegments.count()).toBeGreaterThan(1);
    expect(
        await rootSegments.evaluateAll((segments) =>
            segments.every(
                (segment) =>
                    (segment as HTMLElement).style.clipPath.startsWith('url(') &&
                    segment.classList.contains('backdrop-blur-xl'),
            ),
        ),
    ).toBe(true);
    await expect(page.getByTestId('quick-action-root-rim')).toBeAttached();
    const fanGeometry = await page.getByTestId('quick-action-wheel').evaluate((element) => ({
        mainOuter: Number((element as HTMLElement).dataset.mainOuterRadius),
        fanInner: Number((element as HTMLElement).dataset.outerInnerRadius),
        fanOuter: Number((element as HTMLElement).dataset.wheelOuterRadius),
        label: Number((element as HTMLElement).dataset.outerLabelRadius),
    }));
    expect(fanGeometry.mainOuter - fanGeometry.fanInner).toBeLessThanOrEqual(2);
    expect(fanGeometry.label).toBeGreaterThan((fanGeometry.mainOuter + fanGeometry.fanOuter) / 2);
    expect(fanGeometry.label).toBeLessThan(fanGeometry.fanOuter);
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(0);
    const addNodePosition = await addNodeAction.boundingBox();
    await addNodeAction.locator('[data-root-action-label]').hover();
    await expect(page.locator('[data-action-id="run-all"]')).toBeVisible();
    await expect(page.locator('[data-action-id="fit-graph"]')).toBeVisible();
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(7);
    const outerSegmentStyles = await page.locator('[data-external-quick-action]').evaluateAll((segments) =>
        segments.map((segment) => ({
            accent: (segment as HTMLElement).style.getPropertyValue('--quick-action-accent'),
            zIndex: getComputedStyle(segment).zIndex,
            background: getComputedStyle(segment).backgroundColor,
        })),
    );
    expect(new Set(outerSegmentStyles.map(({ accent }) => accent)).size).toBeGreaterThan(1);
    expect(outerSegmentStyles.every(({ accent, background }) => accent && background !== 'rgba(0, 0, 0, 0)')).toBe(
        true,
    );
    const mainLayerZIndex = await addNodeAction.evaluate((segment) => getComputedStyle(segment).zIndex);
    expect(Number(mainLayerZIndex)).toBeGreaterThan(Number(outerSegmentStyles[0]?.zIndex ?? 0));
    const expandedAddNodePosition = await addNodeAction.boundingBox();
    expect(expandedAddNodePosition?.x).toBeCloseTo(addNodePosition?.x ?? 0, 0);
    expect(expandedAddNodePosition?.y).toBeCloseTo(addNodePosition?.y ?? 0, 0);

    const firstExternalAction = page.locator('[data-external-quick-action]').first();
    await firstExternalAction.locator('[data-external-action-label]').hover();
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(7);
    await page.mouse.move(8, 8);
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(0);

    await addNodeAction.focus();
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(0);
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(7);
    await expect(firstExternalAction).toBeFocused();
    await page.keyboard.press('Backspace');
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(0);
    await expect(addNodeAction).toBeFocused();

    await addNodeAction.locator('[data-root-action-label]').hover();
    await page
        .locator('[data-action-id="add-primary-prompt-text"] [data-external-action-label]')
        .click();
    await expect.poll(async () => (await readCanvasQuickActionState(page)).nodeIds.length).toBe(4);
    expect((await readCanvasQuickActionState(page)).actions).toContain('add-primary-prompt-text');

    await page.locator('.vue-flow__node[data-id="selected-a"]').click({ button: 'right' });
    await expect(page.locator('[data-action-id="copy-selection"]')).toBeVisible();
    await expect(page.locator('[data-action-id="delete-selection"]')).toHaveAttribute(
        'data-danger-action',
        'true',
    );
    await page.keyboard.press('Escape');

    await page.locator('.vue-flow__node[data-id="unselected"]').click({
        button: 'right',
        position: { x: 20, y: 20 },
    });
    await expect(page.locator('[data-action-id="duplicate-node"]')).toBeVisible();
    expect((await readCanvasQuickActionState(page)).selectedIds).toEqual(['unselected']);
});

test('keeps right-drag marquee separate and supports keyboard dismissal', async ({ page }) => {
    const graph = page.getByTestId('canvas-quick-action-graph');
    const box = await graph.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    await page.mouse.move(box.x + 30, box.y + box.height - 120);
    await page.mouse.down({ button: 'right' });
    await page.mouse.move(box.x + 260, box.y + box.height - 300, { steps: 8 });
    await expect(page.getByTestId('fixture-selection-rect')).toBeVisible();
    await page.mouse.up({ button: 'right' });
    await expect(page.getByTestId('quick-action-wheel')).toBeHidden();

    await graph.focus();
    await page.keyboard.press('Shift+F10');
    await expect(page.locator('[data-action-id]').first()).toBeVisible();
    await page.keyboard.press('End');
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('quick-action-wheel')).toBeHidden();
    await expect(graph).toBeFocused();
});

test('bypasses editable content and edges while clamping corner placement', async ({ page }) => {
    await page.getByTestId('editable-node-input').click({ button: 'right' });
    await expect(page.getByTestId('quick-action-wheel')).toBeHidden();

    const edgeHitTarget = page.locator('.vue-flow__edge-interaction').first();
    await edgeHitTarget.click({ button: 'right' });
    await expect(page.getByTestId('quick-action-wheel')).toBeHidden();

    const graph = page.getByTestId('canvas-quick-action-graph');
    const box = await graph.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    await page.mouse.click(box.x + 2, box.y + 2, { button: 'right' });
    const visibleActions = page.locator('[data-action-id]:not([data-external-quick-action])');
    await expect(visibleActions.first()).toBeVisible();
    const viewport = page.viewportSize();
    expect(viewport).not.toBeNull();
    for (const action of await visibleActions.all()) {
        const actionBox = await action.boundingBox();
        expect(actionBox).not.toBeNull();
        if (actionBox && viewport) {
            expect(actionBox.x).toBeGreaterThanOrEqual(0);
            expect(actionBox.y).toBeGreaterThanOrEqual(0);
            expect(actionBox.x + actionBox.width).toBeLessThanOrEqual(viewport.width);
            expect(actionBox.y + actionBox.height).toBeLessThanOrEqual(viewport.height);
        }
    }
    const menuPosition = await page.getByTestId('quick-action-wheel').evaluate((element) => ({
        x: Number.parseFloat((element as HTMLElement).style.left),
        y: Number.parseFloat((element as HTMLElement).style.top),
        radius: Number.parseFloat((element as HTMLElement).dataset.wheelOuterRadius ?? '0'),
    }));
    expect(menuPosition.x - menuPosition.radius).toBeGreaterThanOrEqual(0);
    expect(menuPosition.y - menuPosition.radius).toBeGreaterThanOrEqual(0);
    expect(menuPosition.x + menuPosition.radius).toBeLessThanOrEqual(viewport?.width ?? 0);
    expect(menuPosition.y + menuPosition.radius).toBeLessThanOrEqual(viewport?.height ?? 0);
});
