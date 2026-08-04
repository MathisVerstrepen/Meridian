import {
    expect,
    mountNodePresetsFixture,
    readNodePresetsFixtureState,
    test,
} from '../support/nodePresetsFixture';

test('builds, validates, saves, and reloads account-synced presets', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const { apiState } = await mountNodePresetsFixture(page);
    await page.getByRole('button', { name: 'New', exact: true }).click();
    const names = page.getByLabel('Preset name');
    await names.first().fill('Starter workflow');
    await names.first().blur();
    await page.getByLabel('Choose accent color for Starter workflow').click();
    const colorPicker = page.getByRole('dialog', { name: 'Accent color for Starter workflow' });
    await expect(colorPicker).toBeVisible();
    await colorPicker.getByLabel('Hex').fill('#A1B2C3');
    await expect.poll(async () => (await readNodePresetsFixtureState(page)).nodePresets.presets[0]?.accentColor).toBe('#a1b2c3');
    await page.keyboard.press('Escape');
    await expect(colorPicker).toBeHidden();
    await page.getByRole('button', { name: 'Prompt', exact: true }).click();
    await page.getByRole('button', { name: 'Prompt', exact: true }).click();

    const rail = page.getByLabel('Preset rail');
    const canvas = page.getByLabel('Node preset canvas');
    const palette = canvas.getByLabel('Blocks palette');
    const blockButtons = palette.getByRole('toolbar', { name: 'Add block' }).getByRole('button');
    await expect(palette).toBeVisible();
    await expect(rail).toContainText('1/8');
    await expect(rail).toContainText('2 nodes');
    await expect(rail).not.toContainText('Ready');
    const [railBox, canvasBox, paletteBox, firstBlockBox, secondBlockBox] = await Promise.all([
        rail.boundingBox(),
        canvas.boundingBox(),
        palette.boundingBox(),
        blockButtons.nth(0).boundingBox(),
        blockButtons.nth(1).boundingBox(),
    ]);
    expect(railBox).not.toBeNull();
    expect(canvasBox).not.toBeNull();
    expect(paletteBox).not.toBeNull();
    expect(firstBlockBox).not.toBeNull();
    expect(secondBlockBox).not.toBeNull();
    expect(railBox!.x + railBox!.width).toBeLessThanOrEqual(canvasBox!.x);
    expect(paletteBox!.width).toBeGreaterThan(canvasBox!.width * 0.94);
    expect(secondBlockBox!.x).toBeGreaterThan(firstBlockBox!.x);
    expect(Math.abs(secondBlockBox!.y - firstBlockBox!.y)).toBeLessThan(3);

    const promptNodes = page.locator('.vue-flow__node-prompt');
    await expect(promptNodes).toHaveCount(2);
    await promptNodes.first().getByPlaceholder('Enter your prompt here, or select a template.').fill(
        'Persist this configured prompt',
    );

    await page.getByRole('button', { name: 'New', exact: true }).click();
    await names.nth(1).fill('Temporary preset');
    await names.nth(1).blur();
    const presetCards = page.getByLabel('Node presets').locator('li');
    await presetCards.nth(1).focus();
    await page.keyboard.press('Alt+ArrowUp');
    expect((await readNodePresetsFixtureState(page)).nodePresets.presets.map(({ name }) => name)).toEqual([
        'Temporary preset',
        'Starter workflow',
    ]);
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByLabel('Delete preset').first().click();

    await names.first().fill('');
    await names.first().blur();
    await expect(page.getByRole('alert').first()).toContainText('Preset name must not be blank.');
    await expect(page.getByTestId('save-node-presets')).toBeDisabled();
    expect(apiState.postCount).toBe(0);
    await names.first().fill('Starter workflow');
    await names.first().blur();

    const nodes = page.locator('.vue-flow__node');
    await nodes.first().click({ position: { x: 10, y: 10 } });
    await nodes.nth(1).click({ position: { x: 10, y: 10 }, modifiers: ['Shift'] });
    await page.getByRole('button', { name: 'Group selection' }).click();
    await expect(page.locator('.vue-flow__node-group')).toHaveCount(1);

    await page.getByTestId('save-node-presets').click();
    await expect.poll(() => apiState.postCount).toBe(1);
    expect(apiState.settings.nodePresets.presets[0]?.name).toBe('Starter workflow');
    expect(apiState.settings.nodePresets.presets[0]?.accentColor).toBe('#a1b2c3');
    expect(apiState.settings.nodePresets.presets[0]?.nodes).toHaveLength(3);
    expect(
        apiState.settings.nodePresets.presets[0]?.nodes.some(
            (node) => node.type === 'prompt' && node.data.prompt === 'Persist this configured prompt',
        ),
    ).toBe(true);

    await page.reload();
    await expect(page.getByTestId('node-presets-fixture-page')).toHaveAttribute(
        'data-fixture-ready',
        'true',
    );
    await expect(page.getByLabel('Preset name')).toHaveValue('Starter workflow');
    expect(apiState.getCount).toBeGreaterThanOrEqual(2);
    expect((await readNodePresetsFixtureState(page)).nodePresets.presets[0]?.nodes).toHaveLength(3);
});

test('keeps desktop overflow inside the preset rail list', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 640 });
    const { fixture } = await mountNodePresetsFixture(page);
    const create = page.getByRole('button', { name: 'New', exact: true });
    await create.click();

    const rail = page.getByLabel('Preset rail');
    const list = page.getByLabel('Node presets');
    const canvas = page.getByLabel('Node preset canvas');
    const [railBefore, canvasBefore, fixtureBefore] = await Promise.all([
        rail.boundingBox(),
        canvas.boundingBox(),
        fixture.evaluate((element) => ({
            clientHeight: element.clientHeight,
            scrollHeight: element.scrollHeight,
            scrollTop: element.scrollTop,
        })),
    ]);

    for (let index = 1; index < 8; index += 1) await create.click();
    await expect(page.getByLabel('Preset name')).toHaveCount(8);

    const [railAfter, canvasAfter, fixtureAfter, listBeforeScroll] = await Promise.all([
        rail.boundingBox(),
        canvas.boundingBox(),
        fixture.evaluate((element) => ({
            clientHeight: element.clientHeight,
            scrollHeight: element.scrollHeight,
            scrollTop: element.scrollTop,
        })),
        list.evaluate((element) => ({
            clientHeight: element.clientHeight,
            scrollHeight: element.scrollHeight,
        })),
    ]);
    expect(railBefore).not.toBeNull();
    expect(railAfter).not.toBeNull();
    expect(canvasBefore).not.toBeNull();
    expect(canvasAfter).not.toBeNull();
    expect(Math.abs(railAfter!.height - railBefore!.height)).toBeLessThan(1);
    expect(Math.abs(canvasAfter!.height - canvasBefore!.height)).toBeLessThan(1);
    expect(listBeforeScroll.scrollHeight).toBeGreaterThan(listBeforeScroll.clientHeight);
    expect(fixtureAfter.clientHeight).toBe(fixtureBefore.clientHeight);
    expect(fixtureAfter.scrollHeight).toBe(fixtureBefore.scrollHeight);
    expect(fixtureAfter.scrollHeight).toBe(fixtureAfter.clientHeight);
    expect(fixtureAfter.scrollTop).toBe(0);

    await list.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
    });
    await expect.poll(() => list.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    expect(await fixture.evaluate((element) => element.scrollTop)).toBe(0);
    expect(
        await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight),
    ).toBe(true);
});

test('keeps free-plan GitHub locked and remains usable at narrow keyboard layouts', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.setViewportSize({ width: 720, height: 900 });
    await mountNodePresetsFixture(page);
    await page.getByTestId('set-free-plan').click();
    await page.getByRole('button', { name: 'New', exact: true }).click();

    const github = page.getByRole('button', { name: 'GitHub', exact: true });
    await expect(github).toBeDisabled();
    await expect(github).toHaveAttribute('title', 'GitHub blocks require Premium');
    const scrollLeft = page.getByRole('button', { name: 'Scroll blocks left' });
    const scrollRight = page.getByRole('button', { name: 'Scroll blocks right' });
    await expect(scrollLeft).toBeDisabled();
    await expect(scrollRight).toBeEnabled();
    await scrollRight.click();
    await expect(scrollLeft).toBeEnabled();
    const railBox = await page.getByLabel('Preset rail').boundingBox();
    const canvasBox = await page.getByLabel('Node preset canvas').boundingBox();
    expect(railBox).not.toBeNull();
    expect(canvasBox).not.toBeNull();
    expect(canvasBox!.y).toBeGreaterThanOrEqual(railBox!.y + railBox!.height);
    await page.getByLabel('Preset name').focus();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('Choose accent color for Untitled preset')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByLabel('Delete preset')).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
