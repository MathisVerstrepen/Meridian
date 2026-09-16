import type { Page, TestInfo } from '@playwright/test';
import { expect, mountMarkdownRendererFixture, test } from '../support/markdownRendererFixture';

const captureTableScreenshot = async (page: Page, testInfo: TestInfo, name: string) => {
    const path = testInfo.outputPath(`${name}.png`);
    await page.mouse.move(0, 0);
    await page.screenshot({ path });
    await testInfo.attach(name, { path, contentType: 'image/png' });
};

test('wide sample scrolls locally on narrow screens and expands with sticky headers and keyboard focus', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const { responseContainer } = await mountMarkdownRendererFixture(page, 'tables');
    const scroll = responseContainer.getByRole('region', { name: 'Scrollable table' }).first();
    await expect(scroll.locator('tbody tr')).toHaveCount(25);
    await expect(scroll.locator('tbody td').first()).toHaveCSS('position', 'static');
    const dimensions = await scroll.evaluate((element) => ({
        viewport: element.clientWidth,
        content: element.scrollWidth,
        page: document.documentElement.scrollWidth,
        window: window.innerWidth,
        columns: Array.from(element.querySelectorAll('th')).map((cell) => cell.getBoundingClientRect().width),
    }));
    expect(dimensions.content).toBeGreaterThan(dimensions.viewport);
    expect(dimensions.page).toBeLessThanOrEqual(dimensions.window);
    expect(dimensions.columns[2]).toBeGreaterThan(200);
    expect(dimensions.columns[1]).toBeLessThan(dimensions.columns[2]!);
    await testInfo.attach('narrow-table-layout', { body: JSON.stringify(dimensions), contentType: 'application/json' });
    await captureTableScreenshot(page, testInfo, 'narrow-table');
    expect(await responseContainer.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
    await scroll.focus();
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => scroll.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    await scroll.evaluate((element) => { element.scrollLeft = element.scrollWidth; });
    await scroll.getByText('Data science, machine learning, web backend, automation').scrollIntoViewIfNeeded();
    await expect(scroll.getByText('Data science, machine learning, web backend, automation')).toBeInViewport();

    const expand = responseContainer.getByRole('button', { name: 'Expand table' }).first();
    await expand.click();
    const dialog = page.getByRole('dialog', { name: 'Expanded table' });
    await expect(dialog).toBeVisible();
    const close = dialog.getByRole('button', { name: 'Close expanded table' });
    await expect(close).toBeFocused();
    const expanded = dialog.getByRole('region', { name: 'Expanded table contents' });
    await expect(expanded.locator('tbody tr')).toHaveCount(25);
    const panelSize = await dialog.locator('[id^="headlessui-dialog-panel"]').boundingBox();
    expect(panelSize!.width).toBeGreaterThan(340);
    expect(panelSize!.width).toBeLessThanOrEqual(358);
    expect(panelSize!.height).toBeLessThanOrEqual(812);
    expect(panelSize!.y).toBeGreaterThanOrEqual(16);
    const contentSize = await expanded.boundingBox();
    expect(contentSize!.x - panelSize!.x).toBeGreaterThanOrEqual(16);
    expect(panelSize!.x + panelSize!.width - contentSize!.x - contentSize!.width).toBeGreaterThanOrEqual(16);
    expect(panelSize!.y + panelSize!.height - contentSize!.y - contentSize!.height).toBeGreaterThanOrEqual(16);
    await captureTableScreenshot(page, testInfo, 'narrow-expanded-table');
    const initialHeader = await expanded.locator('thead').boundingBox();
    const corner = expanded.locator('thead th').first();
    const firstCell = expanded.locator('tbody td').first();
    const secondCell = expanded.locator('tbody td').nth(1);
    const initialCorner = await corner.boundingBox();
    const initialFirstCell = await firstCell.boundingBox();
    const initialSecondCell = await secondCell.boundingBox();
    await expanded.evaluate((element) => { element.scrollLeft = 300; });
    expect(await expanded.evaluate((element) => element.scrollLeft)).toBe(300);
    expect(Math.abs((await firstCell.boundingBox())!.x - initialFirstCell!.x)).toBeLessThan(1);
    expect((await secondCell.boundingBox())!.x).toBeLessThan(initialSecondCell!.x - 290);
    await captureTableScreenshot(page, testInfo, 'narrow-pinned-column');
    await expanded.evaluate((element) => { element.scrollTop = 500; element.scrollLeft = 300; });
    expect(await expanded.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    const scrolledHeader = await expanded.locator('thead').boundingBox();
    expect(Math.abs(scrolledHeader!.y - initialHeader!.y)).toBeLessThan(2);
    const scrolledCorner = await corner.boundingBox();
    expect(Math.abs(scrolledCorner!.x - initialCorner!.x)).toBeLessThan(1);
    expect(Math.abs(scrolledCorner!.y - initialCorner!.y)).toBeLessThan(2);
    expect(await corner.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return element.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
    })).toBe(true);
    await page.keyboard.press('Tab');
    await expect(expanded).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(dialog.getByRole('button', { name: 'Copy table', exact: true })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(close).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(expand).toBeFocused();
    await expand.click();
    await close.click();
    await expect(dialog).toHaveCount(0);
    await expect(expand).toBeFocused();
});

test('small tables stay compact and preserve links, alignment, emphasis and escaped code in each view', async ({ page }) => {
    const { responseContainer } = await mountMarkdownRendererFixture(page, 'tables');
    const small = responseContainer.getByRole('region', { name: 'Scrollable table' }).nth(1);
    expect(await small.locator('table').evaluate((table) => table.clientWidth)).toBeLessThan(400);
    expect(await small.evaluate((element) => element.scrollWidth - element.clientWidth)).toBe(0);
    await expect(small.getByRole('link', { name: 'Docs' })).toHaveAttribute('href', 'https://example.com/docs');
    await expect(small.locator('td').nth(1)).toHaveCSS('text-align', 'right');
    await expect(small.locator('td').nth(2)).toHaveCSS('text-align', 'center');
    await responseContainer.getByRole('button', { name: 'Expand table' }).nth(1).click();
    const dialog = page.getByRole('dialog', { name: 'Expanded table' });
    const panel = await dialog.locator('[id^="headlessui-dialog-panel"]').boundingBox();
    expect(panel!.width).toBeLessThan(450);
    expect(panel!.height).toBeLessThan(260);
    await expect(dialog.locator('table')).toHaveCount(1);
    await expect(dialog.locator('strong')).toHaveText('2');
    await expect(dialog.locator('em')).toHaveText('Ready');
    await expect(dialog.getByRole('link', { name: 'Docs' })).toHaveAttribute('href', 'https://example.com/docs');
    await expect(dialog.locator('td').nth(1)).toHaveCSS('text-align', 'right');
    await page.keyboard.press('Escape');
    await responseContainer.getByRole('button', { name: 'Expand table' }).nth(2).click();
    await expect(dialog.locator('code')).toHaveText('<img src=x onerror=alert(1)>');
    await expect(dialog.locator('img')).toHaveCount(0);
});

for (const theme of ['standard', 'light']) {
    test(`finance table fits its content with clear ${theme} theme contrast`, async ({ page }, testInfo) => {
        await page.setViewportSize({ width: 1920, height: 1080 });
        const { responseContainer } = await mountMarkdownRendererFixture(page, 'financeTable');
        if (theme === 'light') {
            await page.evaluate(() => {
                document.documentElement.classList.remove('dark', 'theme-standard');
                document.documentElement.classList.add('theme-light');
            });
        }
        await responseContainer.getByRole('button', { name: 'Expand table' }).click();
        const dialog = page.getByRole('dialog', { name: 'Expanded table' });
        const panel = dialog.locator('[id^="headlessui-dialog-panel"]');
        const contents = dialog.getByRole('region', { name: 'Expanded table contents' });
        await expect(contents.locator('thead th')).toHaveCount(9);
        await expect(contents.locator('tbody tr')).toHaveCount(5);
        const panelBox = await panel.boundingBox();
        const tableBox = await contents.locator('table').boundingBox();
        const toolbarBox = await panel.locator(':scope > div').first().boundingBox();
        await captureTableScreenshot(page, testInfo, `finance-expanded-${theme}`);
        expect(panelBox!.height).toBeLessThan(500);
        expect(panelBox!.width).toBeLessThanOrEqual(1856);
        expect(tableBox!.x - panelBox!.x).toBeGreaterThanOrEqual(20);
        expect(panelBox!.x + panelBox!.width - tableBox!.x - tableBox!.width).toBeGreaterThanOrEqual(20);
        expect(tableBox!.y - toolbarBox!.y - toolbarBox!.height).toBeGreaterThanOrEqual(20);
        expect(panelBox!.y + panelBox!.height - tableBox!.y - tableBox!.height).toBeGreaterThanOrEqual(20);
        expect(await contents.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
        expect(panelBox!.y).toBeGreaterThan(250);
        expect(Math.abs(panelBox!.x + panelBox!.width / 2 - 960)).toBeLessThan(2);
        const headerColor = await contents.locator('thead').evaluate((element) => getComputedStyle(element).backgroundColor);
        const surfaceColor = await panel.evaluate((element) => getComputedStyle(element).backgroundColor);
        expect(headerColor).toBe(surfaceColor);
        await expect(contents.locator('tbody td').first()).toHaveCSS('border-bottom-width', '1px');
        await expect(contents.locator('tbody td').first()).toHaveCSS('border-bottom-style', 'solid');
        await expect(contents.locator('tbody td').nth(1)).toHaveCSS('text-align', 'right');
        await expect(contents.locator('tbody tr').last().locator('td').last()).toBeInViewport({ ratio: 1 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(1920);
        // Resize to force horizontal overflow, checking opaque pinned cells in both themes.
        await page.setViewportSize({ width: 900, height: 700 });
        const firstColumn = contents.locator('tbody tr > td:first-child');
        const beforeScroll = await firstColumn.first().boundingBox();
        await contents.evaluate((element) => { element.scrollLeft = 500; });
        expect(await contents.evaluate((element) => element.scrollLeft)).toBe(500);
        expect(Math.abs((await firstColumn.first().boundingBox())!.x - beforeScroll!.x)).toBeLessThan(1);
        for (const cell of [firstColumn.nth(0), firstColumn.nth(1)]) {
            const colors = await cell.evaluate((element) => ({
                cell: getComputedStyle(element).backgroundColor,
                row: getComputedStyle(element.parentElement!).backgroundColor,
            }));
            expect(colors.cell).toBe(colors.row);
            expect(colors.cell).not.toBe('rgba(0, 0, 0, 0)');
        }
        const stripeColor = await firstColumn.nth(1).evaluate((element) => getComputedStyle(element).backgroundColor);
        await firstColumn.nth(1).hover();
        const hoverColors = await firstColumn.nth(1).evaluate((element) => ({
            cell: getComputedStyle(element).backgroundColor,
            row: getComputedStyle(element.parentElement!).backgroundColor,
        }));
        expect(hoverColors.cell).toBe(hoverColors.row);
        expect(hoverColors.cell).not.toBe(stripeColor);
        await captureTableScreenshot(page, testInfo, `finance-pinned-${theme}`);
        await page.keyboard.press('Escape');
        await expect(responseContainer.getByRole('button', { name: 'Expand table' })).toBeFocused();
    });
}

test('streamed tables settle without duplicate controls or lost cells', async ({ page }) => {
    const { fixturePage, responseContainer } = await mountMarkdownRendererFixture(page, 'tables', { streaming: true });
    await expect(fixturePage).toHaveAttribute('data-streaming-done', 'true');
    await expect(responseContainer.getByRole('button', { name: 'Expand table' })).toHaveCount(3);
    await expect(responseContainer.locator('table').first().locator('tbody tr')).toHaveCount(25);
    await responseContainer.getByRole('button', { name: 'Expand table' }).first().click();
    await expect(page.getByRole('dialog').locator('tbody tr')).toHaveCount(25);
});

test('copy offers three formats for the displayed snapshot and resets when reopened', async ({ page, context }, testInfo) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.setViewportSize({ width: 320, height: 700 });
    const { responseContainer } = await mountMarkdownRendererFixture(page, 'tables');
    const expand = responseContainer.getByRole('button', { name: 'Expand table' });
    await expand.nth(1).click();
    const dialog = page.getByRole('dialog', { name: 'Expanded table' });
    const copy = dialog.getByRole('button', { name: 'Copy table', exact: true });
    await expect(copy).toBeInViewport({ ratio: 1 });
    await expect(dialog.getByRole('button', { name: 'Close expanded table' })).toBeInViewport({ ratio: 1 });
    const copyBox = await copy.boundingBox();
    const closeBox = await dialog.getByRole('button', { name: 'Close expanded table' }).boundingBox();
    expect(copyBox!.x + copyBox!.width).toBeLessThanOrEqual(closeBox!.x);
    expect(copyBox!.y).toBe(closeBox!.y);
    // Updating the source while open must not change the snapshot being copied.
    await responseContainer.locator('table').nth(1).locator('td').first().evaluate((cell) => { cell.textContent = 'Changed'; });
    await copy.click();
    const menu = dialog.getByRole('menu');
    await expect(menu.getByRole('menuitem')).toHaveText(['Markdown', 'TSV', 'CSV']);
    await expect(menu.getByRole('menuitem', { name: 'CSV', exact: true })).toBeInViewport({ ratio: 1 });
    await captureTableScreenshot(page, testInfo, 'copy-format-menu');
    await menu.getByRole('menuitem', { name: 'TSV', exact: true }).click();
    await expect(dialog.getByRole('status')).toHaveText('Table copied');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('Link\tCount\tStatus\nDocs\t2\tReady');
    await expect(menu).toHaveCount(0);
    const copied = dialog.getByRole('button', { name: 'Table copied', exact: true });
    await expect(copied).toBeFocused();
    for (const [format, expected] of [
        ['CSV', 'Link,Count,Status\r\nDocs,2,Ready'],
        ['Markdown', '| Link | Count | Status |\n| --- | --- | --- |\n| Docs | 2 | Ready |'],
    ]) {
        await copied.click();
        await menu.getByRole('menuitem', { name: format, exact: true }).click();
        await expect(dialog.getByRole('status')).toHaveText('Table copied');
        expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expected);
    }
    // Menu Escape must return focus without dismissing its parent dialog.
    await copied.press('ArrowDown');
    await expect(menu).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    await expect(dialog).toBeVisible();
    await expect(copied).toBeFocused();
    await copied.press('ArrowDown');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await expect(menu).toHaveCount(0);
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('Link\tCount\tStatus\nDocs\t2\tReady');
    await page.keyboard.press('Escape');
    await expand.nth(2).click();
    await expect(dialog.getByRole('status')).toBeEmpty();
    await dialog.getByRole('button', { name: 'Copy table', exact: true }).click();
    await dialog.getByRole('menuitem', { name: 'Markdown', exact: true }).click();
    await expect(dialog.getByRole('status')).toHaveText('Table copied');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('| Literal |\n| --- |\n| &lt;img src=x onerror=alert(1)&gt; |');
    await expect(dialog.locator('img')).toHaveCount(0);
});

test('copy reports clipboard denial and allows retry with all offscreen rows and columns', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const { responseContainer } = await mountMarkdownRendererFixture(page, 'tables');
    await responseContainer.getByRole('button', { name: 'Expand table' }).first().click();
    const dialog = page.getByRole('dialog', { name: 'Expanded table' });
    await page.evaluate(() => {
        const original = navigator.clipboard.writeText.bind(navigator.clipboard);
        navigator.clipboard.writeText = async (text: string) => {
            navigator.clipboard.writeText = original;
            throw new DOMException(`Denied ${text.length} characters`, 'NotAllowedError');
        };
    });
    const copy = dialog.getByRole('button', { name: 'Copy table', exact: true });
    await copy.click();
    await dialog.getByRole('menuitem', { name: 'CSV', exact: true }).click();
    await expect(dialog.getByRole('status')).toHaveText('Copy failed. Clipboard unavailable.');
    await expect(copy).toBeEnabled();
    await copy.click();
    await dialog.getByRole('menuitem', { name: 'TSV', exact: true }).click();
    await expect(dialog.getByRole('status')).toHaveText('Table copied');
    const text = await page.evaluate(() => navigator.clipboard.readText());
    const rows = text.split('\n');
    expect(rows).toHaveLength(26);
    for (const row of rows) expect(row.split('\t')).toHaveLength(7);
    expect(rows[1]).toContain('Python');
    expect(rows.at(-1)).toContain('Zig');
});
