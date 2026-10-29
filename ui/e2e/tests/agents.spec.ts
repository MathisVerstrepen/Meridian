import {
    test as diagnosticsTest,
    expect,
    startBrowserDiagnostics,
    formatBrowserDiagnostics,
} from '../support/browserDiagnosticsFixture';
import type { Page } from '@playwright/test';

const route = '/auth/agent-fixture';
const profiles = ['Helper', 'Reviewer'].map((name, index) => ({
    id: `agent-${index}`,
    handle: name.toLowerCase(),
    profile: {
        name,
        handle: name.toLowerCase(),
        lifecycle: 'active',
        icon: 'LucideBot',
        description: name,
    },
}));
const mockLibrary = async (page: Page) => {
    await page.route('**/api/agents?**', (r) =>
        r.fulfill({ json: { items: profiles, total: profiles.length } }),
    );
    await page.route('**/api/agents/teams', (r) =>
        r.fulfill({
            json: [
                {
                    id: 'default-team',
                    name: 'Default Team',
                    handle: 'default',
                    is_default: true,
                    members: ['agent-0', 'agent-1'],
                },
                {
                    id: 'team-1',
                    name: 'Research Team',
                    handle: 'research',
                    is_default: false,
                    members: ['agent-1'],
                },
            ],
        }),
    );
    await page.route('**/api/agents/resolve-mention', (r) => {
        // SAFETY: resolveMention sends a JSON object with its validated message string.
        const message = (r.request().postDataJSON() as { message: string }).message;
        if (/^@research\s+@/.test(message) || message.startsWith('@unknown')) {
            return r.fulfill({ status: 400, json: { detail: 'Choose one known Team handle.' } });
        }
        return r.fulfill({
            json: { team_id: 'team-1', message: message.replace(/^@research\s*/, '') },
        });
    });
};
const test = diagnosticsTest.extend<Record<string, never>, { agentBootstrap: true }>({
    agentBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const page = await browser.newPage();
            const diagnostics = startBrowserDiagnostics(page);
            try {
                await mockLibrary(page);
                await page.goto(new URL(route, String(workerInfo.project.use.baseURL)).toString(), {
                    timeout: 120_000,
                });
                await expect(page.getByTestId('agent-fixture')).toHaveAttribute(
                    'data-ready',
                    'true',
                    { timeout: 120_000 },
                );
            } catch (error) {
                throw new Error(
                    `Agent fixture bootstrap failed. ${formatBrowserDiagnostics(diagnostics.report)}`,
                    { cause: error },
                );
            } finally {
                diagnostics.stop();
                await page.close();
            }
            await use(true);
        },
        { scope: 'worker', auto: true, timeout: 120_000 },
    ],
});

test.beforeEach(async ({ page }) => {
    await mockLibrary(page);
    await page.goto(route);
    await expect(page.getByTestId('agent-fixture')).toHaveAttribute('data-ready', 'true');
});

test('Agent configuration always selects one Team and defaults to the account Team @smoke', async ({
    page,
}) => {
    const team = page.getByLabel('Agent Team', { exact: true });
    await expect(team).toHaveValue('default-team');
    await expect(team.locator('option[value=""]')).toHaveCount(0);
    await expect(page.getByRole('checkbox', { name: /as subagent/ })).toHaveCount(0);
    const model = page.getByRole('combobox', { name: 'Model', exact: true });
    await model.fill('Fast');
    await page.getByRole('option', { name: /Meridian Fast/ }).click();
    await team.selectOption('team-1');
    await expect(page.getByTestId('configuration')).toHaveText('fixture/fast / team-1');
    await team.selectOption('default-team');
    await expect(page.getByTestId('configuration')).toHaveText('fixture/fast / default-team');
});

test('leading mention autocomplete and errors preserve input before mutation @smoke', async ({
    page,
}) => {
    const input = page.locator('[contenteditable]');
    await input.fill('@res');
    await page.getByRole('option', { name: '@research · Research Team' }).click();
    await expect(input).toHaveText('@research');
    await input.fill('@unknown task');
    await input.press('Enter');
    await expect(page.getByTestId('mention-status')).toHaveText('Choose one known Team handle.');
    await expect(page.getByTestId('mutation-count')).toHaveText('0');
    await expect(input).toHaveText('@unknown task');
    await input.fill('@research @default task');
    await input.press('Enter');
    await expect(page.getByTestId('mutation-count')).toHaveText('0');
    await input.fill('@research task');
    await input.press('Enter');
    await expect(page.getByTestId('mutation-count')).toHaveText('1');
    await expect(page.getByLabel('Agent Team', { exact: true })).toHaveValue('team-1');
});

test('parallel subagent runs retain distinct instructions results tools and status @smoke', async ({
    page,
}) => {
    await page.getByRole('button', { name: 'Start parallel batch' }).click();
    await expect(page.locator('[data-run-id="primary-run"]')).toHaveCount(0);
    await expect(page.getByTestId('subagent-disclosure-button')).toHaveCount(2);
    await expect(page.getByTestId('subagent-disclosure-panel')).toHaveCount(0);
    const thinking = page.getByTestId('thinking-disclosure-button');
    const activity = page.locator('[aria-label="Subagent activity"]');
    const answer = page.getByTestId('markdown-renderer-response');
    const thinkingBox = await thinking.boundingBox();
    const activityBox = await activity.boundingBox();
    const answerBox = await answer.boundingBox();
    expect(thinkingBox && activityBox && answerBox).toBeTruthy();
    expect(thinkingBox!.y).toBeLessThan(activityBox!.y);
    expect(activityBox!.y).toBeLessThan(answerBox!.y);

    const first = page.locator('[data-run-id="first"]');
    const second = page.locator('[data-run-id="second"]');
    await first.getByTestId('subagent-disclosure-button').click();
    await second.getByTestId('subagent-disclosure-button').click();
    await expect(first).toContainText('Find evidence');
    await expect(second).toContainText('Review findings');
    await page.getByRole('button', { name: 'Finish first run' }).click();
    await expect(first).toContainText('Completed');
    await expect(first).toContainText('Evidence collected');
    await expect(first).not.toContainText('Researcher · web_search');
    await expect(first.locator('details')).toHaveCount(0);
    await expect(second).toContainText('Running');
    await expect(second).not.toContainText('Evidence collected');
    await first.getByTestId('subagent-disclosure-button').focus();
    await page.keyboard.press('Enter');
    await expect(first.getByTestId('subagent-disclosure-button')).toHaveAttribute(
        'aria-expanded',
        'false',
    );
    await expect(second.getByTestId('subagent-disclosure-button')).toHaveAttribute(
        'aria-expanded',
        'true',
    );
});

test('canvas configuration keeps its Team visible without tool controls @smoke', async ({
    page,
}) => {
    await page.goto(`${route}?view=node`);
    await expect(page.getByTestId('agent-fixture')).toHaveAttribute('data-ready', 'true');
    await expect(page.getByLabel('Agent Team', { exact: true })).toHaveValue('default-team');
    await expect(page.getByText('What can it do?', { exact: true })).not.toBeVisible();
    await expect(page.getByText('Main model tools', { exact: false })).toHaveCount(0);
    await expect(page.getByRole('checkbox')).toHaveCount(0);
    await page.getByLabel('Agent Team', { exact: true }).selectOption('team-1');
    await expect(page.getByTestId('configuration')).toHaveText('fixture/default / team-1');
});

test('expanded subagent output is bounded, opens at the end and respects reading position @smoke', async ({
    page,
}) => {
    await page.getByRole('button', { name: 'Start long subagent' }).click();
    const first = page.locator('[data-run-id="first"]');
    const toggle = first.getByTestId('subagent-disclosure-button');
    await toggle.click();
    const output = first.getByRole('region', { name: 'Researcher subagent output' });
    await expect(output).toContainText('Latest finding.');
    const bottomGap = () =>
        output.evaluate(
            (element) => element.scrollHeight - element.clientHeight - element.scrollTop,
        );
    await expect.poll(bottomGap).toBeLessThan(2);
    const dimensions = await output.evaluate((element) => ({
        height: element.clientHeight,
        full: element.scrollHeight,
    }));
    expect(dimensions.full).toBeGreaterThan(dimensions.height);
    expect(dimensions.height).toBeLessThanOrEqual(
        Math.min(page.viewportSize()!.height * 0.6, 512) + 1,
    );
    await output.evaluate((element) => {
        element.scrollTop = 0;
        element.dispatchEvent(new Event('scroll'));
    });
    await page.getByRole('button', { name: 'Append finding' }).click();
    await expect(output).toContainText('New streamed finding 1.');
    expect(await output.evaluate((element) => element.scrollTop)).toBeLessThan(2);
    await toggle.click();
    await toggle.click();
    await expect.poll(bottomGap).toBeLessThan(2);
    await page.getByRole('button', { name: 'Append finding' }).click();
    await expect(output).toContainText('New streamed finding 2.');
    await expect.poll(bottomGap).toBeLessThan(2);
});

test('Agent sidebar uses the Text-to-Text six-tool tile picker @smoke', async ({ page }) => {
    await page.goto(`${route}?view=sidebar`);
    await expect(page.getByTestId('agent-fixture')).toHaveAttribute('data-ready', 'true');
    for (const name of [
        'Web Search',
        'Link Extraction',
        'Media Gen',
        'Execute Code',
        'Visualise',
        'Ask User',
    ])
        await expect(page.getByRole('button', { name, exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Manage Agent Teams' })).toHaveAttribute(
        'href',
        '/settings?tab=Agent&view=teams',
    );
    await expect(page.getByLabel('Team members', { exact: true })).toContainText('Helper');
    await expect(page.getByLabel('Team members', { exact: true })).toContainText('Reviewer');
    await page.getByRole('button', { name: 'Web Search', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Web Search', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
    );
    await expect(
        page.getByRole('button', { name: 'Link Extraction', exact: true }),
    ).toHaveAttribute('aria-pressed', 'true');
    for (const name of ['Main model', 'Team', 'Tools']) {
        const heading = page.getByRole('heading', { name: new RegExp(`^${name}(?:$| )`) });
        await expect(heading).toBeVisible();
        await expect(heading).toHaveClass(/bg-obsidian\/20/);
    }
    await expect(page.getByTestId('selected-tools')).toContainText('web_search');
    await expect(page.getByTestId('selected-tools')).toContainText('link_extraction');
    await page.getByRole('button', { name: 'Web Search', exact: true }).click();
    await expect(page.getByTestId('selected-tools')).toBeEmpty();
    const auto = page.getByRole('switch', { name: 'Auto Tool Selection' });
    await expect(auto).not.toBeChecked();
    await auto.click();
    await expect(auto).toBeChecked();
    await expect(page.getByTestId('auto-select-tools')).toHaveText('true');
    await expect(page.getByRole('button', { name: 'Web Search', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Ask User', exact: true })).toBeDisabled();
    await auto.click();
    await expect(page.getByTestId('auto-select-tools')).toHaveText('false');
    await expect(page.getByRole('button', { name: 'Ask User', exact: true })).toBeEnabled();
});

test('Agent canvas restores the original sand palette and keeps tools off the node @smoke', async ({
    page,
}, testInfo) => {
    await page.goto(`${route}?view=canvas`);
    const node = page.locator('.vue-flow__node-agent');
    await expect(node.locator('.bg-sunbaked-sand')).toHaveCSS(
        'background-color',
        'rgb(212, 193, 168)',
    );
    await expect(node.getByLabel('Agent Team', { exact: true })).toHaveValue('default-team');
    await expect(node.getByRole('combobox', { name: 'Model', exact: true })).toBeVisible();
    await expect(node.getByText('Main model tools', { exact: false })).toHaveCount(0);
    await expect(node.getByRole('button', { name: 'Web Search', exact: true })).toHaveCount(0);
    await expect(
        node.getByLabel('Agent Team', { exact: true }).locator('option:checked'),
    ).toHaveText('Default Team (2 subagents)');
    await expect(node.getByText('available subagents', { exact: false })).toHaveCount(0);
    await expect(node.getByRole('group', { name: 'Executed subagents' })).toHaveText(
        'Subagents: Researcher, Reviewer',
    );
    await expect(node.getByTestId('subagent-disclosure-button')).toHaveCount(0);
    await expect(node.getByTestId('subagent-disclosure-panel')).toHaveCount(0);
    await node.screenshot({ path: testInfo.outputPath('agent-node-sand.png') });
});

test('Team mention picker supports arrows Tab Enter and Escape without premature submission @smoke', async ({
    page,
}, testInfo) => {
    const input = page.getByRole('textbox', { name: 'Chat message', exact: true });
    const menu = page.getByTestId('team-mention-menu');
    await input.fill('@');
    await expect(menu).toBeVisible();
    await expect(menu).toContainText('Tab / ↵');
    const defaultTeam = page.getByRole('option', { name: '@default · Default Team', exact: true });
    const research = page.getByRole('option', { name: '@research · Research Team', exact: true });
    await expect(defaultTeam).toHaveAttribute('aria-selected', 'true');
    await input.press('ArrowDown');
    await expect(research).toHaveAttribute('aria-selected', 'true');
    await expect(input).toHaveAttribute(
        'aria-activedescendant',
        (await research.getAttribute('id')) ?? '',
    );
    await input.press('Tab');
    await expect(input).toBeFocused();
    await expect(input).toHaveText('@research');
    await expect(menu).toHaveCount(0);
    await expect(page.getByTestId('mutation-count')).toHaveText('0');
    await input.pressSequentially('Find sources');
    await expect(input).toHaveText('@research Find sources');
    await input.fill('@def');
    await input.press('Enter');
    await expect(input).toHaveText('@default');
    await expect(menu).toHaveCount(0);
    await expect(page.getByTestId('mutation-count')).toHaveText('0');
    await input.fill('@res');
    await input.press('Escape');
    await expect(menu).toHaveCount(0);
    await input.press('Tab');
    await expect(input).not.toBeFocused();
    await input.fill('hello @');
    await expect(menu).toHaveCount(0);
    await input.fill('@');
    await input.evaluate((el) =>
        el.dispatchEvent(
            new KeyboardEvent('keydown', {
                key: 'Enter',
                isComposing: true,
                bubbles: true,
                cancelable: true,
            }),
        ),
    );
    await expect(input).toHaveText('@');
    await expect(menu).toBeVisible();
    await expect(page.getByTestId('mutation-count')).toHaveText('0');
    await menu.screenshot({ path: testInfo.outputPath('team-mention-menu.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    const menuBox = await menu.boundingBox();
    expect(menuBox).toBeTruthy();
    expect(menuBox!.x).toBeGreaterThanOrEqual(0);
    expect(menuBox!.x + menuBox!.width).toBeLessThanOrEqual(390);
});

test('Team mention completion preserves existing task text and accepts case-insensitive queries @smoke', async ({
    page,
}) => {
    const input = page.getByRole('textbox', { name: 'Chat message', exact: true });
    await input.fill('@RES');
    await expect(
        page.getByRole('option', { name: '@research · Research Team', exact: true }),
    ).toBeVisible();
    await input.press('Tab');
    await expect(input).toHaveText('@research');
    await input.fill('@res existing task');
    await input.evaluate((el) => {
        const range = document.createRange();
        range.setStart(el.firstChild!, 4);
        range.collapse(true);
        window.getSelection()?.removeAllRanges();
        window.getSelection()?.addRange(range);
        el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    await expect(page.getByRole('listbox', { name: 'Team mentions' })).toBeVisible();
    await input.press('Tab');
    await expect(input).toHaveText('@research existing task');
    await input.pressSequentially('new ');
    await expect(input).toHaveText('@research new existing task');
    await input.fill('@unknown');
    await expect(page.getByTestId('team-mention-menu')).toContainText('No Teams match @unknown');
    await input.press('Enter');
    await expect(page.getByTestId('mutation-count')).toHaveText('0');
    await expect(input).toHaveText('@unknown');
});
