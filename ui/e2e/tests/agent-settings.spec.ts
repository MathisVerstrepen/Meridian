import type { Page } from '@playwright/test';
import { AGENT_SETTINGS_PRESETS } from '../fixtures/agentSettingsFixture';
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
    await page.route('**/api/agents/presets', (r) => r.fulfill({ json: AGENT_SETTINGS_PRESETS }));
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
    await expect(editor).toContainText('@web-researcher-2');
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
    await editor.getByRole('checkbox', { name: 'Web search', exact: true }).check();
    await expect(editor.getByRole('checkbox', { name: 'Read links', exact: true })).toBeChecked();
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

test('templates prefill role instructions and tools while Save draft stays private @smoke', async ({
    page,
}) => {
    const saved = await mockSettings(page);
    await mountSettings(page);
    await page.getByRole('button', { name: 'Use Research Agent template', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await expect(editor.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue(
        'Research Agent',
    );
    await expect(editor.getByRole('textbox', { name: 'Agent instructions' })).toHaveValue(
        'Research using primary sources and cite the evidence.',
    );
    await expect(editor.getByRole('checkbox', { name: 'Web search', exact: true })).toBeChecked();
    await editor.getByRole('button', { name: 'Save draft', exact: true }).click();
    await expect.poll(() => saved.length).toBe(1);
    expect(saved[0]).toMatchObject({
        lifecycle: 'draft',
        visibility: 'private',
        handle: 'research-agent',
    });
});

test('custom handles are preserved and failed saves keep the draft @smoke', async ({ page }) => {
    await mockSettings(page, { conflict: true });
    await mountSettings(page);
    await page.getByRole('button', { name: '+ Create Agent', exact: true }).click();
    const editor = page.getByRole('form', { name: 'Agent editor' });
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Research');
    await editor.getByRole('button', { name: 'Edit handle' }).click();
    await editor.getByRole('textbox', { name: 'Agent handle', exact: true }).fill('my-helper');
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Renamed Researcher');
    await editor
        .getByRole('textbox', { name: 'Agent instructions' })
        .fill('Keep these instructions.');
    await expect(editor.getByRole('textbox', { name: 'Agent handle', exact: true })).toHaveValue(
        'my-helper',
    );
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
