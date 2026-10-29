import type { Page } from '@playwright/test';
import type { AgentRecord } from '../../app/types/agent';
import { ToolEnum } from '../../app/types/enums';
import { createAgentDraft } from '../../app/utils/agentEditor';
import { isJsonObject } from '../../app/utils/runtimeTypes';
import {
    test as diagnosticsTest,
    expect,
    startBrowserDiagnostics,
    formatBrowserDiagnostics,
} from '../support/browserDiagnosticsFixture';

const fixtureRoute = '/auth/agent-fixture?view=settings';
const existingProfile = {
    ...createAgentDraft('fixture/default'),
    name: 'Web Researcher',
    handle: 'web-researcher',
};
const record = (profile = existingProfile) => ({
    id: '00000000-0000-4000-8000-000000000010',
    owner_id: 'owner',
    author: 'You',
    handle: profile.handle,
    profile,
    version: 1,
    verified: false,
    source_id: null,
    source_version: null,
    rating_count: 0,
    rating_average: 0,
    bookmark_count: 0,
    fork_count: 0,
    usage_count: 0,
    bookmarked: false,
    my_rating: null,
});

async function mockSettings(page: Page, options: { existing?: boolean; conflict?: boolean } = {}) {
    const saved: JsonObject[] = [];
    const profiles = options.existing ? [record()] : [];
    await page.route('**/api/agents?**', (r) =>
        r.fulfill({ json: { items: profiles, total: profiles.length } }),
    );
    await page.route('**/api/agents/teams', (r) => r.fulfill({ json: [] }));
    await page.route('**/api/agents', async (r) => {
        const body: JsonValue = r.request().postDataJSON();
        if (!isJsonObject(body)) throw new Error('Agent request must be a JSON object');
        saved.push(body);
        if (options.conflict)
            return r.fulfill({ status: 409, json: { detail: 'This handle is already in use.' } });
        return r.fulfill({ json: { ...record(), profile: body, handle: body.handle } });
    });
    return saved;
}

async function mountSettings(page: Page) {
    await page.goto(fixtureRoute);
    await expect(page.getByTestId('agent-fixture')).toHaveAttribute('data-ready', 'true');
}

const test = diagnosticsTest.extend<Record<string, never>, { settingsBootstrap: true }>({
    settingsBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const page = await browser.newPage();
            const diagnostics = startBrowserDiagnostics(page);
            try {
                await mockSettings(page);
                await page.goto(
                    new URL(fixtureRoute, String(workerInfo.project.use.baseURL)).toString(),
                    { timeout: 120_000 },
                );
                await expect(page.getByTestId('agent-fixture')).toHaveAttribute(
                    'data-ready',
                    'true',
                    { timeout: 120_000 },
                );
                await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
                await expect(
                    page.getByRole('combobox', { name: 'Model', exact: true }),
                ).toHaveValue('Meridian Balanced', { timeout: 120_000 });
            } catch (error) {
                throw new Error(
                    `Agent Settings bootstrap failed. ${formatBrowserDiagnostics(diagnostics.report)}`,
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

test('create an Agent with a suggested handle default model and explicit tool choices @smoke', async ({
    page,
}, testInfo) => {
    const saved = await mockSettings(page, { existing: true });
    await mountSettings(page);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await expect(page.getByRole('navigation', { name: 'Agent library views' })).not.toBeVisible();
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Web Researcher');
    await expect(editor).not.toContainText('@web-researcher');
    await expect(editor.getByRole('button', { name: 'Edit handle' })).toHaveCount(0);
    await expect(
        editor.getByRole('textbox', { name: 'Agent handle', exact: true }),
    ).not.toBeVisible();
    await editor
        .getByRole('textbox', { name: 'Agent instructions' })
        .fill('Research carefully and cite your sources.');
    await expect(editor.getByRole('combobox', { name: 'Model', exact: true })).toHaveValue(
        'Meridian Balanced',
    );
    await expect(
        editor.getByRole('spinbutton', { name: 'Temperature', exact: true }),
    ).not.toBeVisible();
    await editor.getByRole('button', { name: 'Web search', exact: true }).click();
    await expect(editor.getByRole('button', { name: 'Read links', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
    );
    await expect(
        editor
            .getByRole('group', { name: 'What can it do?', exact: true })
            .locator('input[type=checkbox]'),
    ).toHaveCount(0);
    await editor
        .getByRole('button', { name: 'Agent library', exact: true })
        .scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath('agent-creation.png') });
    await editor.getByRole('button', { name: 'Create Agent', exact: true }).click();
    await expect.poll(() => saved.length).toBe(1);
    expect(saved[0]).toMatchObject({
        name: 'Web Researcher',
        handle: 'web-researcher-2',
        lifecycle: 'active',
        visibility: 'private',
        tools: ['web_search', 'link_extraction'],
        model_settings: { model: 'fixture/default' },
        prompt_stack: [{ text: 'Research carefully and cite your sources.', enabled: true }],
    });
    await expect(page.getByRole('heading', { name: 'Your Agent library' })).toBeVisible();
});

test('creation has no starter templates and Save draft stays private @smoke', async ({ page }) => {
    const saved = await mockSettings(page);
    let presetRequests = 0;
    page.on('request', (request) => {
        if (request.url().includes('/api/agents/presets')) presetRequests += 1;
    });
    await mountSettings(page);
    await expect(page.getByText(/starter templates|start with a template/i)).toHaveCount(0);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await expect(editor.getByText(/template/i)).toHaveCount(0);
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Research Agent');
    await editor
        .getByRole('textbox', { name: 'Agent instructions' })
        .fill('Find reliable sources.');
    await editor.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect.poll(() => saved.length).toBe(1);
    expect(saved[0]).toMatchObject({
        lifecycle: 'draft',
        visibility: 'private',
        handle: 'research-agent',
    });
    expect(presetRequests).toBe(0);
});

test('internal handle collisions retry and failed saves keep the draft @smoke', async ({
    page,
}) => {
    await mockSettings(page, { conflict: true });
    await mountSettings(page);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Research');
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Renamed Researcher');
    await editor
        .getByRole('textbox', { name: 'Agent instructions' })
        .fill('Keep these instructions.');
    await expect(editor.getByRole('textbox', { name: 'Agent handle', exact: true })).toHaveCount(0);
    await editor.getByRole('button', { name: 'Create Agent', exact: true }).click();
    await expect(editor.getByRole('alert').first()).toContainText('already in use');
    await expect(editor.getByRole('textbox', { name: 'Agent instructions' })).toHaveValue(
        'Keep these instructions.',
    );
    await expect(editor.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue(
        'Renamed Researcher',
    );
});

test('searchable models advanced overrides and visual customization remain available @smoke', async ({
    page,
}) => {
    const saved = await mockSettings(page);
    await mountSettings(page);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Creative Helper');
    const models = editor.getByRole('combobox', { name: 'Model', exact: true });
    await models.fill('Fast');
    await page.getByRole('option', { name: /Meridian Fast/ }).click();
    await editor.locator('summary').filter({ hasText: 'Appearance & organization' }).click();
    await editor.getByRole('button', { name: 'Design icon', exact: true }).click();
    await editor.getByRole('button', { name: 'Use accent #6788be', exact: true }).click();
    await editor.locator('summary').filter({ hasText: 'Advanced model settings' }).click();
    await editor.getByRole('spinbutton', { name: 'Temperature', exact: true }).fill('0.3');
    await editor.getByRole('button', { name: 'Create Agent', exact: true }).click();
    await expect.poll(() => saved.length).toBe(1);
    expect(saved[0]).toMatchObject({
        icon: 'MaterialSymbolsPaletteOutline',
        accentColor: '#6788be',
        model_settings: { model: 'fixture/fast', temperature: 0.3 },
    });
});

test('creation remains usable on a narrow screen without horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockSettings(page);
    await mountSettings(page);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toBeVisible();
    expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.getByRole('button', { name: 'Create Agent', exact: true }).scrollIntoViewIfNeeded();
    await expect(page.getByRole('button', { name: 'Create Agent', exact: true })).toBeInViewport();
});

test('Teams panel searches reorders removes and saves members and creates Teams @smoke', async ({
    page,
}, testInfo) => {
    await mockSettings(page, { existing: true });
    const helper = record();
    const reviewer = {
        ...record({ ...existingProfile, name: 'Reviewer', handle: 'reviewer' }),
        id: '00000000-0000-4000-8000-000000000011',
    };
    const teams = [
        {
            id: 'default-team',
            name: 'Default Team',
            handle: 'default',
            is_default: true,
            description: '',
            members: [helper.id],
        },
    ];
    const writes: JsonObject[] = [];
    await page.route('**/api/agents?**', (r) =>
        r.fulfill({ json: { items: [helper, reviewer], total: 2 } }),
    );
    await page.route('**/api/agents/teams', async (r) => {
        if (r.request().method() === 'GET') return r.fulfill({ json: teams });
        const body: JsonValue = r.request().postDataJSON();
        if (!isJsonObject(body)) throw new Error('Expected Team object');
        writes.push(body);
        const entry = {
            id: 'new-team',
            is_default: false,
            name: String(body.name),
            handle: String(body.handle),
            description: String(body.description),
            members: [reviewer.id],
        };
        teams.push(entry);
        return r.fulfill({ json: entry });
    });
    await page.route('**/api/agents/teams/default-team', async (r) => {
        const body: JsonValue = r.request().postDataJSON();
        if (!isJsonObject(body)) throw new Error('Expected Team object');
        writes.push(body);
        teams[0] = { ...teams[0]!, name: String(body.name), members: [reviewer.id] };
        return r.fulfill({ json: teams[0] });
    });
    await mountSettings(page);
    await page.getByRole('button', { name: 'Manage Teams', exact: true }).click();
    const form = page.getByRole('form', { name: 'Team editor' });
    await expect(form.getByRole('textbox', { name: 'Team handle', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: '+ Create Agent' })).toHaveCount(0);
    await form.getByRole('searchbox', { name: 'Add Agents' }).fill('review');
    await form.getByRole('button', { name: 'Add Reviewer', exact: true }).click();
    await form.getByRole('button', { name: 'Move Reviewer up', exact: true }).click();
    const members = form.getByRole('region', { name: 'Team members' }).locator('ol > li');
    await expect(members.first()).toContainText('Reviewer');
    await form.getByRole('button', { name: 'Remove Web Researcher', exact: true }).click();
    await form.getByRole('button', { name: 'Save Team', exact: true }).click();
    await expect(page.getByRole('status')).toHaveText('Team saved.');
    expect(writes[0]).toEqual({
        name: 'Default Team',
        handle: 'default',
        description: '',
        members: [reviewer.id],
    });
    await page.getByRole('button', { name: '+ Create Team', exact: true }).click();
    await form.getByRole('textbox', { name: 'Team name', exact: true }).fill('Review Team');
    await expect(form.getByRole('textbox', { name: 'Team handle', exact: true })).toHaveValue(
        'review-team',
    );
    await form.getByRole('button', { name: 'Add Reviewer', exact: true }).click();
    await form.getByRole('button', { name: 'Save Team', exact: true }).click();
    await expect(
        page
            .getByRole('navigation', { name: 'Your Teams' })
            .getByRole('button', { name: /Review Team/ }),
    ).toHaveAttribute('aria-current', 'true');
    expect(writes[1]).toMatchObject({ name: 'Review Team', members: [reviewer.id] });
    await page.screenshot({ path: testInfo.outputPath('agent-teams-panel.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await expect(form.getByRole('button', { name: 'Save Team', exact: true })).toBeVisible();
});

test('description generation is available after instructions and preserves manual edits @smoke', async ({
    page,
}) => {
    await mockSettings(page);
    let release: (() => void) | undefined;
    let captured: JsonValue = null;
    const pending = new Promise<void>((resolve) => {
        release = resolve;
    });
    await page.route('**/api/agents/generate-description', async (r) => {
        captured = r.request().postDataJSON();
        await pending;
        await r.fulfill({
            json: { description: 'Researches reliable sources and cites evidence.' },
        });
    });
    await mountSettings(page);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    const generate = editor.getByRole('button', { name: 'Generate Agent description' });
    await expect(generate).toHaveCount(0);
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Researcher');
    await editor
        .getByRole('textbox', { name: 'Agent instructions' })
        .fill('Find reliable sources and cite evidence.');
    await generate.click();
    await expect(generate).toBeDisabled();
    const description = editor.getByRole('textbox', {
        name: 'What does it help with? Optional',
        exact: true,
    });
    await description.fill('My own description');
    release?.();
    await expect(editor.getByRole('alert')).toContainText('draft changed');
    await expect(description).toHaveValue('My own description');
    await generate.click();
    await expect(description).toHaveValue('Researches reliable sources and cites evidence.');
    expect(captured).toEqual({
        name: 'Researcher',
        instructions: 'Find reliable sources and cite evidence.',
        model: 'fixture/default',
    });
    const model = editor.getByRole('combobox', { name: 'Model', exact: true });
    const trigger = editor.locator('.ui-models-trigger').first();
    const [inputBox, triggerBox] = await Promise.all([model.boundingBox(), trigger.boundingBox()]);
    expect(
        Math.abs(inputBox!.y + inputBox!.height / 2 - (triggerBox!.y + triggerBox!.height / 2)),
    ).toBeLessThanOrEqual(1);
    await page.unroute('**/api/agents/generate-description');
    await page.route('**/api/agents/generate-description', (r) =>
        r.fulfill({ status: 502, json: { detail: 'Please try again.' } }),
    );
    await generate.click();
    await expect(editor.getByRole('alert')).toHaveText('Please try again.');
    await expect(description).toHaveValue('Researches reliable sources and cites evidence.');
});

test('editing shows a visibility chip and a responsive save bar with pending feedback @smoke', async ({
    page,
}, testInfo) => {
    await page.setViewportSize({ width: 1360, height: 900 });
    await mockSettings(page, { existing: true });
    const entry = record();
    await page.route(`**/api/agents/${entry.id}/versions`, (r) => r.fulfill({ json: [] }));
    let release: (() => void) | undefined;
    const pending = new Promise<void>((resolve) => {
        release = resolve;
    });
    await page.route(`**/api/agents/${entry.id}`, async (r) => {
        const body: JsonValue = r.request().postDataJSON();
        await pending;
        return r.fulfill({ json: { ...entry, profile: body, version: 2 } });
    });
    await mountSettings(page);
    await page.getByRole('button', { name: 'Edit Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    const preview = editor.getByRole('complementary', { name: 'Agent preview' });
    const privateChip = preview.getByLabel('Agent visibility: Private');
    await expect(privateChip).toHaveText('Private');
    await expect(privateChip.locator('svg')).toHaveCount(1);
    await expect(preview).not.toContainText('Only you can access');
    await expect(preview).not.toContainText('Default Team');
    await editor.locator('summary').filter({ hasText: 'Visibility & availability' }).click();
    await editor.getByRole('combobox', { name: /^Visibility/ }).selectOption('public');
    await expect(preview.getByLabel('Agent visibility: Public')).toHaveText('Public');
    await expect(preview.getByLabel('Agent visibility: Public').locator('svg')).toHaveCount(1);
    const bar = editor.locator('footer[aria-label="Agent save actions"]');
    const save = bar.getByRole('button', { name: 'Save changes', exact: true });
    await expect(bar).toHaveCSS('position', 'sticky');
    await expect(bar).toHaveCSS('backdrop-filter', 'none');
    await expect(bar).toContainText('Editing v1');
    await editor
        .getByRole('button', { name: 'Agent library', exact: true })
        .scrollIntoViewIfNeeded();
    await expect(save).toBeInViewport();
    await page.screenshot({ path: testInfo.outputPath('agent-save-bar-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await save.scrollIntoViewIfNeeded();
    await expect(save).toBeInViewport();
    await expect(bar.getByRole('button', { name: 'Cancel', exact: true })).toBeInViewport();
    expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('agent-save-bar-mobile.png') });
    await save.click();
    await expect(bar.getByRole('status')).toHaveText('Saving your Agent…');
    await expect(bar.getByRole('button', { name: 'Saving…', exact: true })).toBeDisabled();
    await expect(bar.getByRole('button', { name: 'Cancel', exact: true })).toBeDisabled();
    release?.();
    await expect(page.getByRole('heading', { name: 'Your Agent library' })).toBeVisible();
});

test('library preview shows readable metadata and updates ratings and bookmarks @smoke', async ({
    page,
}, testInfo) => {
    await mockSettings(page, { existing: true });
    let current: AgentRecord = {
        ...record(),
        usage_count: 12,
        profile: {
            ...existingProfile,
            description: 'Researches sources and summarizes the evidence.',
            tags: ['research'],
            tools: [ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION],
            prompt_stack: [
                {
                    name: 'Research instructions',
                    text: Array.from(
                        { length: 100 },
                        (_, i) => `Research step ${i + 1}: verify the evidence.`,
                    ).join('\n'),
                    enabled: true,
                },
                { name: 'Optional style', text: 'Use short paragraphs.', enabled: false },
            ],
        },
    };
    await page.route('**/api/agents?**', (r) =>
        r.fulfill({ json: { items: [current], total: 1 } }),
    );
    await page.route(`**/api/agents/${current.id}/bookmark`, (r) => {
        current = { ...current, bookmarked: r.request().method() === 'PUT' };
        return r.fulfill({ json: { bookmarked: current.bookmarked } });
    });
    await page.route(`**/api/agents/${current.id}/rating`, (r) => {
        const body: JsonValue = r.request().postDataJSON();
        if (!isJsonObject(body)) throw new Error('Expected rating');
        const value = Number(body.value);
        current = { ...current, my_rating: value, rating_average: value, rating_count: 1 };
        return r.fulfill({ json: { rating: value } });
    });
    await mountSettings(page);
    const card = page
        .locator('article')
        .filter({ has: page.getByRole('button', { name: 'Preview Web Researcher', exact: true }) });
    await expect(
        card.getByRole('button', { name: 'Edit Agent', exact: true }).locator('svg'),
    ).toHaveCount(1);
    await expect(card).not.toContainText('@web-researcher');
    const trigger = card.getByRole('button', { name: 'Preview', exact: true });
    await trigger.click();
    const preview = page.getByRole('region', { name: 'Agent preview', exact: true });
    await expect(
        preview.getByRole('heading', { name: 'Web Researcher', exact: true }),
    ).toBeFocused();
    await expect(preview.getByRole('region', { name: 'Agent model preview' })).toContainText(
        'Meridian Balanced',
    );
    await expect(preview.getByRole('region', { name: 'Agent tools preview' })).toContainText(
        'Web search',
    );
    await expect(preview).not.toContainText('link_extraction');
    const instructions = preview
        .getByRole('region', { name: 'Agent instructions preview' })
        .locator('.overflow-y-auto');
    const dimensions = await instructions.evaluate((el) => ({
        client: el.clientHeight,
        scroll: el.scrollHeight,
    }));
    expect(dimensions.client).toBeLessThanOrEqual(288);
    expect(dimensions.scroll).toBeGreaterThan(dimensions.client);
    await preview.getByRole('button', { name: 'Rate 4 of 5', exact: true }).click();
    await expect(preview.getByRole('button', { name: 'Rate 4 of 5', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
    );
    await expect(preview).toContainText('4.0 / 5');
    await preview.getByRole('button', { name: 'Bookmark', exact: true }).click();
    await expect(preview.getByRole('button', { name: 'Bookmarked', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
    );
    await preview.getByRole('button', { name: 'Rate 2 of 5', exact: true }).click();
    await expect(preview).toContainText('2.0 / 5');
    expect(current.rating_count).toBe(1);
    await page.screenshot({ path: testInfo.outputPath('agent-library-preview.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await preview.getByRole('button', { name: 'Close Agent preview' }).click();
    await expect(preview).toHaveCount(0);
    await expect(trigger).toBeFocused();
    const more = card.locator('summary');
    await more.click();
    await expect(card.getByRole('button', { name: 'Export JSON', exact: true })).toBeVisible();
    await more.press('Escape');
    await expect(card.getByRole('button', { name: 'Export JSON', exact: true })).not.toBeVisible();
});

test('custom SVG icons are previewed applied saved and restored alongside preset choices @smoke', async ({
    page,
}, testInfo) => {
    await mockSettings(page, { existing: true });
    let current: AgentRecord = record();
    const svg =
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="10" cy="10" r="6"/><path d="M15 15l5 5"/></svg>';
    let generated: JsonValue = null;
    let saved: JsonValue = null;
    let release: (() => void) | undefined;
    const pending = new Promise<void>((resolve) => {
        release = resolve;
    });
    await page.route('**/api/agents?**', (r) =>
        r.fulfill({ json: { items: [current], total: 1 } }),
    );
    await page.route(`**/api/agents/${current.id}/versions`, (r) => r.fulfill({ json: [] }));
    await page.route('**/api/agents/generate-icon', async (r) => {
        generated = r.request().postDataJSON();
        await pending;
        return r.fulfill({ json: { iconSvg: svg } });
    });
    await page.route(`**/api/agents/${current.id}`, (r) => {
        const body: AgentRecord['profile'] = r.request().postDataJSON();
        saved = r.request().postDataJSON();
        current = { ...current, profile: body, version: 2 };
        return r.fulfill({ json: current });
    });
    await mountSettings(page);
    await page.getByRole('button', { name: 'Edit Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await editor
        .getByRole('textbox', { name: 'Agent instructions' })
        .fill('Research reliable sources and compare the evidence.');
    await editor.locator('summary').filter({ hasText: 'Appearance & organization' }).click();
    await editor.getByRole('button', { name: 'Generate icon', exact: true }).click();
    await expect(editor.getByRole('button', { name: 'Save changes', exact: true })).toBeDisabled();
    release?.();
    await expect(editor.getByRole('img', { name: 'Generated SVG icon' })).toBeVisible();
    expect(generated).toMatchObject({
        name: 'Web Researcher',
        instructions: 'Research reliable sources and compare the evidence.',
        model: 'fixture/default',
    });
    await editor.getByRole('button', { name: 'Use icon', exact: true }).click();
    await expect(
        editor.getByRole('button', { name: 'Custom SVG icon', exact: true }),
    ).toHaveAttribute('aria-pressed', 'true');
    await editor.getByRole('button', { name: 'Use accent #6788be', exact: true }).click();
    await expect(
        editor.getByRole('complementary', { name: 'Agent preview' }).locator('img'),
    ).toHaveAttribute('src', /%236788be/);
    await editor.getByRole('button', { name: 'Design icon', exact: true }).click();
    await expect(
        editor.getByRole('complementary', { name: 'Agent preview' }).locator('img'),
    ).toHaveCount(0);
    await editor.getByRole('button', { name: 'Custom SVG icon', exact: true }).click();
    await page.screenshot({ path: testInfo.outputPath('agent-custom-icon-picker.png') });
    await editor.getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Your Agent library' })).toBeVisible();
    expect(saved).toMatchObject({ iconSvg: svg, accentColor: '#6788be' });
    await expect(page.locator('article img')).toHaveAttribute('src', /data:image\/svg\+xml/);
    await page.getByRole('button', { name: 'Edit Agent', exact: true }).click();
    await editor.locator('summary').filter({ hasText: 'Appearance & organization' }).click();
    await expect(
        editor.getByRole('button', { name: 'Custom SVG icon', exact: true }),
    ).toHaveAttribute('aria-pressed', 'true');
});

test('icon generation preserves the existing icon on failure or changed draft context @smoke', async ({
    page,
}) => {
    await mockSettings(page, { existing: true });
    const entry = record();
    await page.route(`**/api/agents/${entry.id}/versions`, (r) => r.fulfill({ json: [] }));
    let release: (() => void) | undefined;
    const pending = new Promise<void>((resolve) => {
        release = resolve;
    });
    await page.route('**/api/agents/generate-icon', async (r) => {
        await pending;
        return r.fulfill({
            json: { iconSvg: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>' },
        });
    });
    await mountSettings(page);
    await page.getByRole('button', { name: 'Edit Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await editor.locator('summary').filter({ hasText: 'Appearance & organization' }).click();
    await editor.getByRole('button', { name: 'Generate icon', exact: true }).click();
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Renamed Agent');
    release?.();
    await expect(editor.getByRole('alert')).toContainText('details changed');
    await expect(editor.getByRole('button', { name: 'Use icon', exact: true })).toHaveCount(0);
    await page.unroute('**/api/agents/generate-icon');
    await page.route('**/api/agents/generate-icon', (r) =>
        r.fulfill({ status: 502, json: { detail: 'Could not generate an icon. Try again.' } }),
    );
    await editor.getByRole('button', { name: 'Generate icon', exact: true }).click();
    await expect(editor.getByRole('alert')).toContainText('Try again');
    await expect(
        editor.getByRole('complementary', { name: 'Agent preview' }).locator('img'),
    ).toHaveCount(0);
    await expect(editor.getByRole('button', { name: 'Save changes', exact: true })).toBeEnabled();
});
