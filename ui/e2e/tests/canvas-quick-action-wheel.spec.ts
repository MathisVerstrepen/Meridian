import {
    expect,
    mountCanvasQuickActionFixture,
    readCanvasQuickActionState,
    test,
} from '../support/canvasQuickActionWheelFixture';

test.beforeEach(async ({ page }) => {
    await mountCanvasQuickActionFixture(page);
});

test('auto layout is stable from controls and canvas wheel', async ({ page }) => {
    await page.getByTestId('seed-mixed-workflow').click();
    await expect.poll(async () => (await readCanvasQuickActionState(page)).nodeIds.length).toBe(6);
    const edgeBefore = (await readCanvasQuickActionState(page)).edges;
    await page.getByTitle('Auto layout').click();
    await expect
        .poll(async () => (await readCanvasQuickActionState(page)).actions)
        .toContain('controls-auto-layout');
    const controlsState = await readCanvasQuickActionState(page);
    const controlsPositions = controlsState.nodes.map(({ id, position }) => ({ id, position }));
    const node = (id: string) => controlsState.nodes.find((candidate) => candidate.id === id)!;
    const centerX = (id: string) => node(id).position.x + node(id).width / 2;
    const centerY = (id: string) => node(id).position.y + node(id).height / 2;
    for (const id of [
        'prompt1',
        'attachment-file',
        'attachment-github',
        'generator1',
        'prompt2',
        'generator2',
    ]) {
        expect(node(id)).toBeDefined();
        expect(node(id).width).toBeGreaterThan(0);
        expect(node(id).height).toBeGreaterThan(0);
    }
    expect(node('generator1').position.y - (node('prompt1').position.y + node('prompt1').height)).toBe(
        100,
    );
    expect(node('attachment-file').position.y + node('attachment-file').height + 40).toBe(
        node('attachment-github').position.y,
    );
    const attachmentRight = node('attachment-file').position.x + node('attachment-file').width;
    expect(attachmentRight).toBe(
        node('attachment-github').position.x + node('attachment-github').width,
    );
    expect(
        (node('attachment-file').position.y +
            node('attachment-github').position.y +
            node('attachment-github').height) /
            2,
    ).toBe(centerY('generator1'));
    expect(
        Math.min(node('prompt1').position.x, node('generator1').position.x) - attachmentRight,
    ).toBeGreaterThanOrEqual(160);
    expect(node('prompt2').position.y - (node('generator1').position.y + node('generator1').height)).toBe(
        100,
    );
    expect(centerX('generator1')).toBe(centerX('generator2'));
    expect(node('generator2').position.y - (node('prompt2').position.y + node('prompt2').height)).toBe(
        100,
    );
    for (let leftIndex = 0; leftIndex < controlsState.nodes.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < controlsState.nodes.length; rightIndex += 1) {
            const left = controlsState.nodes[leftIndex]!;
            const right = controlsState.nodes[rightIndex]!;
            const overlaps =
                left.position.x < right.position.x + right.width &&
                left.position.x + left.width > right.position.x &&
                left.position.y < right.position.y + right.height &&
                left.position.y + left.height > right.position.y;
            expect(overlaps).toBe(false);
        }
    }
    expect(controlsState.edges).toEqual(edgeBefore);
    expect(Object.values(controlsState.viewport).every(Number.isFinite)).toBe(true);

    await page.getByTestId('seed-mixed-workflow').click();
    await expect.poll(async () => (await readCanvasQuickActionState(page)).actions).toEqual([]);
    const wheelEdgesBefore = (await readCanvasQuickActionState(page)).edges;
    const graph = page.getByTestId('canvas-quick-action-graph');
    const box = await graph.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    await page.mouse.click(box.x + box.width - 30, box.y + box.height - 30, {
        button: 'right',
    });
    const autoLayoutAction = page.locator('[data-action-id="auto-layout"]');
    await expect(autoLayoutAction).toBeVisible();
    await autoLayoutAction.locator('[data-root-action-label]').click();
    await expect
        .poll(async () => (await readCanvasQuickActionState(page)).actions)
        .toContain('auto-layout');

    const wheelState = await readCanvasQuickActionState(page);
    expect(wheelState.nodes.map(({ id, position }) => ({ id, position }))).toEqual(
        controlsPositions,
    );
    expect(wheelState.edges).toEqual(wheelEdgesBefore);
    expect(wheelState.edges).toEqual(edgeBefore);
    expect(Object.values(wheelState.viewport).every(Number.isFinite)).toBe(true);
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
    await expect(page.locator('[data-action-id="presets"]')).toHaveCount(0);
    const rootSegments = page.locator('[data-root-quick-action-segment]');
    expect(await rootSegments.count()).toBeGreaterThan(1);
    expect(
        await rootSegments.evaluateAll((segments) =>
            segments.every(
                (segment) =>
                    getComputedStyle(segment).clipPath.startsWith('url(') &&
                    segment.classList.contains('backdrop-blur-xl'),
            ),
        ),
    ).toBe(true);
    await expect(page.getByTestId('quick-action-root-rim')).toBeAttached();
    const fanGeometry = await page.getByTestId('quick-action-wheel').evaluate((element) => ({
        mainOuter: Number(element.getAttribute('data-main-outer-radius')),
        fanInner: Number(element.getAttribute('data-outer-inner-radius')),
        fanOuter: Number(element.getAttribute('data-wheel-outer-radius')),
        label: Number(element.getAttribute('data-outer-label-radius')),
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
            accent: getComputedStyle(segment).getPropertyValue('--quick-action-accent'),
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

    const quickWorkflows = page.locator('[data-action-id="quick-workflows"]');
    await expect(quickWorkflows).toBeVisible();
    await quickWorkflows.locator('[data-root-action-label]').hover();
    await expect(page.locator('[data-external-quick-action]')).toHaveCount(9);
    expect(
        await page.locator('[data-external-quick-action]').evaluateAll((actions) =>
            actions.map((action) => action.getAttribute('data-action-id')),
        ),
    ).toEqual([
        'workflow-attachment-target-0',
        'workflow-attachment-target-1',
        'workflow-context-target-0',
        'workflow-context-target-1',
        'workflow-context-target-2',
        'workflow-prompt-target-0',
        'workflow-context-source-0',
        'workflow-context-source-1',
        'workflow-context-source-2',
    ]);
    const workflow = page.locator('[data-action-id="workflow-context-target-0"]');
    await expect(workflow).toHaveAttribute('aria-label', 'Context input handle · Text to Text node');
    await expect(workflow).toHaveAttribute('title', 'Context input handle · Text to Text node');
    await expect(workflow.locator('[data-compact-workflow-label]')).toHaveText('');
    const handleIndicator = workflow.locator('[data-workflow-handle-indicator]');
    await expect(handleIndicator).toHaveAttribute('data-handle-category', 'context');
    await expect(handleIndicator).toHaveAttribute('data-handle-direction', 'target');
    expect(await handleIndicator.evaluate((element) => getComputedStyle(element).backgroundColor)).toBe(
        'var(--color-node-cat-context)',
    );
    expect(
        await workflow.evaluate((element) =>
            getComputedStyle(element).getPropertyValue('--quick-action-accent'),
        ),
    ).toBe('var(--color-olive-grove)');
    await workflow.locator('[data-external-action-label]').click();
    await expect.poll(async () => (await readCanvasQuickActionState(page)).nodeIds.length).toBe(6);
    expect((await readCanvasQuickActionState(page)).actions).toContain(
        'workflow-context-target-0',
    );
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
        x: Number.parseFloat(getComputedStyle(element).left),
        y: Number.parseFloat(getComputedStyle(element).top),
        radius: Number.parseFloat(element.getAttribute('data-wheel-outer-radius') ?? '0'),
    }));
    expect(menuPosition.x - menuPosition.radius).toBeGreaterThanOrEqual(0);
    expect(menuPosition.y - menuPosition.radius).toBeGreaterThanOrEqual(0);
    expect(menuPosition.x + menuPosition.radius).toBeLessThanOrEqual(viewport?.width ?? 0);
    expect(menuPosition.y + menuPosition.radius).toBeLessThanOrEqual(viewport?.height ?? 0);
});

test('places grouped presets twice with fresh IDs, remapped handles, and cleared output', async ({ page }) => {
    await page.getByTestId('seed-valid-preset').click();
    const graph = page.getByTestId('canvas-quick-action-graph');
    const box = await graph.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    const placementPoint = { x: box.x + box.width / 2, y: box.y + box.height * 0.72 };

    const placePreset = async () => {
        await page.mouse.click(placementPoint.x, placementPoint.y, { button: 'right' });
        const presets = page.locator('[data-action-id="presets"]');
        await expect(presets).toBeVisible();
        await presets.locator('[data-root-action-label]').hover();
        const action = page.locator(
            '[data-action-id="preset-10000000-0000-4000-8000-000000000001"]',
        );
        await expect(action).toHaveAttribute('aria-label', 'Grouped responder');
        expect(
            await action.evaluate((element) =>
                getComputedStyle(element).getPropertyValue('--quick-action-accent').trim(),
            ),
        ).toBe('#3366aa');
        await action.locator('[data-external-action-label]').click();
    };

    await placePreset();
    await expect.poll(async () => (await readCanvasQuickActionState(page)).nodeIds.length).toBe(6);
    const first = await readCanvasQuickActionState(page);
    const firstPlaced = first.nodes.filter(
        (node) => !['selected-a', 'selected-b', 'unselected'].includes(node.id),
    );
    expect(firstPlaced).toHaveLength(3);
    const firstGroup = firstPlaced.find((node) => node.type === 'group');
    const firstPrompt = firstPlaced.find((node) => node.type === 'prompt');
    const firstGenerator = firstPlaced.find((node) => node.type === 'textToText');
    expect(firstGroup?.data).toMatchObject({
        comment: '<strong>plain group</strong>',
        contentMode: 'plain',
    });
    expect(firstPrompt?.parentNode).toBe(firstGroup?.id);
    expect(firstGenerator?.data).toMatchObject({
        model: 'fixture/model',
        reply: '',
        usageData: null,
    });
    const firstPresetEdge = first.edges.find((edge) => edge.id !== 'fixture-edge');
    expect(firstPresetEdge).toMatchObject({
        source: firstPrompt?.id,
        target: firstGenerator?.id,
        sourceHandle: `prompt_${firstPrompt?.id}`,
        targetHandle: `prompt_${firstGenerator?.id}`,
    });
    expect(first.selectedIds.sort()).toEqual(firstPlaced.map((node) => node.id).sort());
    const firstRootBoxes = await Promise.all(
        [firstGroup?.id, firstGenerator?.id].map((id) =>
            page.locator(`.vue-flow__node[data-id="${id}"]`).boundingBox(),
        ),
    );
    expect(firstRootBoxes.every((rootBox) => rootBox !== null)).toBe(true);
    const rootLeft = Math.min(...firstRootBoxes.map((rootBox) => rootBox?.x ?? Infinity));
    const rootTop = Math.min(...firstRootBoxes.map((rootBox) => rootBox?.y ?? Infinity));
    const rootRight = Math.max(
        ...firstRootBoxes.map((rootBox) => (rootBox?.x ?? 0) + (rootBox?.width ?? 0)),
    );
    const rootBottom = Math.max(
        ...firstRootBoxes.map((rootBox) => (rootBox?.y ?? 0) + (rootBox?.height ?? 0)),
    );
    expect((rootLeft + rootRight) / 2).toBeCloseTo(placementPoint.x, -1);
    expect((rootTop + rootBottom) / 2).toBeCloseTo(placementPoint.y, -1);

    await placePreset();
    await expect.poll(async () => (await readCanvasQuickActionState(page)).nodeIds.length).toBe(9);
    const second = await readCanvasQuickActionState(page);
    const allPlaced = second.nodes.filter(
        (node) => !['selected-a', 'selected-b', 'unselected'].includes(node.id),
    );
    expect(new Set(allPlaced.map((node) => node.id)).size).toBe(6);
    expect(second.edges.filter((edge) => edge.id !== 'fixture-edge')).toHaveLength(2);
    const rootPositions = allPlaced
        .filter((node) => !node.parentNode)
        .map((node) => `${node.position.x}:${node.position.y}`);
    expect(new Set(rootPositions).size).toBeGreaterThan(2);
});

test('hides invalid presets and blocks the complete GitHub preset on free plans', async ({ page }) => {
    const graph = page.getByTestId('canvas-quick-action-graph');
    const box = await graph.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    const point = { x: box.x + box.width - 60, y: box.y + box.height - 60 };

    await page.getByTestId('seed-invalid-preset').click();
    await page.mouse.click(point.x, point.y, { button: 'right' });
    await expect(page.locator('[data-action-id="presets"]')).toHaveCount(0);
    await page.keyboard.press('Escape');

    await page.getByTestId('seed-github-preset').click();
    await page.mouse.click(point.x, point.y, { button: 'right' });
    const presets = page.locator('[data-action-id="presets"]');
    await presets.locator('[data-root-action-label]').hover();
    const locked = page.locator(
        '[data-action-id="preset-10000000-0000-4000-8000-000000000002"]',
    );
    await expect(locked).toHaveAttribute('aria-label', 'Repository review (Premium)');
    const before = await readCanvasQuickActionState(page);
    await locked.locator('[data-external-action-label]').click();
    await expect(page.getByText('GitHub nodes are available on the Premium plan.')).toBeVisible();
    expect((await readCanvasQuickActionState(page)).nodeIds).toEqual(before.nodeIds);
});
