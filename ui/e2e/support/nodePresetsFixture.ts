import type { Page } from '@playwright/test';

import type { Settings } from '../../app/types/settings';
import {
    createNodePresetFixtureSettings,
    NODE_PRESETS_FIXTURE_ROUTE,
} from '../fixtures/nodePresetsFixture';
import {
    expect as baseExpect,
    formatBrowserDiagnostics,
    startBrowserDiagnostics,
    test as diagnosticsTest,
} from './browserDiagnosticsFixture';

interface WorkerFixtures {
    nodePresetsBootstrap: true;
}

export interface NodePresetsFixtureState {
    ready: boolean;
    plan: 'free' | 'premium' | null;
    hasChanged: boolean;
    saveBlocked: boolean;
    lastSaveSucceeded: boolean | null;
    nodePresets: Settings['nodePresets'];
}

export interface NodePresetsApiState {
    settings: Settings;
    getCount: number;
    postCount: number;
}

const apiStates = new WeakMap<Page, NodePresetsApiState>();
const COLD_BOOTSTRAP_TIMEOUT = 120_000;
const NAVIGATION_TIMEOUT = 20_000;
const HYDRATION_TIMEOUT = 90_000;

const installApiMock = async (page: Page): Promise<NodePresetsApiState> => {
    const existing = apiStates.get(page);
    if (existing) return existing;
    const state: NodePresetsApiState = {
        settings: createNodePresetFixtureSettings(),
        getCount: 0,
        postCount: 0,
    };
    apiStates.set(page, state);
    await page.route('**/api/user/settings', async (route) => {
        if (route.request().method() === 'POST') {
            state.settings = structuredClone(route.request().postDataJSON() as Settings);
            state.postCount += 1;
            await route.fulfill({ json: state.settings });
            return;
        }
        state.getCount += 1;
        await route.fulfill({ json: state.settings });
    });
    await page.route('**/api/prompt-templates/library/combined', (route) =>
        route.fulfill({ json: { created: [], bookmarked: [] } }),
    );
    await page.route('**/api/models', (route) =>
        route.fulfill({ json: { version: 1, data: [] } }),
    );
    await page.route('**/api/inference/providers/status', (route) =>
        route.fulfill({ json: { providers: [] } }),
    );
    await page.route('**/api/auth/github/status', (route) =>
        route.fulfill({ json: { isConnected: false } }),
    );
    await page.route('**/api/_auth/session', (route) =>
        route.fulfill({
            json: {
                id: 'node-presets-fixture-session',
                user: {
                    id: 'fixture-user',
                    oauthId: 'fixture-oauth',
                    email: 'fixture@example.com',
                    name: 'Fixture User',
                    avatarUrl: '',
                    provider: 'userpass',
                    plan_type: 'premium',
                    is_admin: false,
                    is_verified: true,
                    has_seen_welcome: true,
                },
            },
        }),
    );
    return state;
};

export const expect = baseExpect;
export const test = diagnosticsTest.extend<Record<string, never>, WorkerFixtures>({
    nodePresetsBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const context = await browser.newContext();
            const page = await context.newPage();
            const diagnostics = startBrowserDiagnostics(page);
            try {
                await installApiMock(page);
                const baseURL = workerInfo.project.use.baseURL;
                if (typeof baseURL !== 'string') throw new Error('Fixture requires configured baseURL');
                await page.goto(new URL(NODE_PRESETS_FIXTURE_ROUTE, baseURL).toString(), {
                    timeout: NAVIGATION_TIMEOUT,
                });
                await baseExpect(page.getByTestId('node-presets-fixture-page')).toHaveAttribute(
                    'data-fixture-ready',
                    'true',
                    { timeout: HYDRATION_TIMEOUT },
                );
            } catch (error) {
                throw new Error(
                    `Node Presets cold bootstrap failed.\n\n${formatBrowserDiagnostics(diagnostics.report)}`,
                    { cause: error },
                );
            } finally {
                diagnostics.stop();
                await context.close().catch(() => undefined);
            }
            await use(true);
        },
        { scope: 'worker', auto: true, timeout: COLD_BOOTSTRAP_TIMEOUT },
    ],
});

export const mountNodePresetsFixture = async (page: Page) => {
    const apiState = await installApiMock(page);
    await page.goto(NODE_PRESETS_FIXTURE_ROUTE);
    const fixture = page.getByTestId('node-presets-fixture-page');
    await expect(fixture).toHaveAttribute('data-fixture-ready', 'true', { timeout: 30_000 });
    return { fixture, apiState };
};

export const readNodePresetsFixtureState = async (page: Page): Promise<NodePresetsFixtureState> =>
    JSON.parse(
        (await page.getByTestId('node-presets-fixture-state').textContent()) ?? '{}',
    ) as NodePresetsFixtureState;
