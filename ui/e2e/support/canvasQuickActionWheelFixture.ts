import type { Page } from '@playwright/test';

import { CANVAS_QUICK_ACTION_FIXTURE_ROUTE } from '../fixtures/canvasQuickActionWheelFixture';
import {
    expect as baseExpect,
    formatBrowserDiagnostics,
    startBrowserDiagnostics,
    test as diagnosticsTest,
} from './browserDiagnosticsFixture';

interface WorkerFixtures {
    canvasQuickActionBootstrap: true;
}

export interface CanvasQuickActionState {
    nodeIds: string[];
    selectedIds: string[];
    nodes: Array<{
        id: string;
        type?: string;
        position: { x: number; y: number };
        parentNode?: string;
        data: Record<string, unknown>;
    }>;
    edges: Array<{
        id: string;
        source: string;
        target: string;
        sourceHandle?: string | null;
        targetHandle?: string | null;
    }>;
    presetNames: string[];
    plan: 'free' | 'premium' | null;
    actions: string[];
    selecting: boolean;
}

const COLD_BOOTSTRAP_TIMEOUT = 120_000;
const NAVIGATION_TIMEOUT = 20_000;
const HYDRATION_TIMEOUT = 90_000;
export const expect = baseExpect;
export const test = diagnosticsTest.extend<Record<string, never>, WorkerFixtures>({
    canvasQuickActionBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const context = await browser.newContext();
            const page = await context.newPage();
            const diagnostics = startBrowserDiagnostics(page);
            try {
                const baseURL = workerInfo.project.use.baseURL;
                if (typeof baseURL !== 'string') throw new Error('Fixture requires configured baseURL');
                await page.goto(new URL(CANVAS_QUICK_ACTION_FIXTURE_ROUTE, baseURL).toString(), {
                    timeout: NAVIGATION_TIMEOUT,
                });
                await baseExpect(page.getByTestId('canvas-quick-action-fixture-page')).toHaveAttribute(
                    'data-fixture-ready',
                    'true',
                    { timeout: HYDRATION_TIMEOUT },
                );
            } catch (error) {
                throw new Error(
                    `Canvas quick-action cold bootstrap failed.\n\n${formatBrowserDiagnostics(diagnostics.report)}`,
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

export const mountCanvasQuickActionFixture = async (page: Page) => {
    await page.goto(CANVAS_QUICK_ACTION_FIXTURE_ROUTE);
    const fixture = page.getByTestId('canvas-quick-action-fixture-page');
    await expect(fixture).toHaveAttribute('data-fixture-ready', 'true', { timeout: 30_000 });
    return fixture;
};

export const readCanvasQuickActionState = async (page: Page): Promise<CanvasQuickActionState> =>
    JSON.parse(
        (await page.getByTestId('canvas-quick-action-state').textContent()) ?? '{}',
    ) as CanvasQuickActionState;
