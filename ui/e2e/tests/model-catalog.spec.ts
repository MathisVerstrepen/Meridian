import { test as baseTest, type Locator, type Page } from '@playwright/test';
import { MODEL_CAPABILITY_BITS, MODEL_SUPPORTED_TOOL_BITS } from '../../app/types/modelCatalog';
import {
    expect,
    test as diagnosticsTest,
    startBrowserDiagnostics,
    formatBrowserDiagnostics,
} from '../support/browserDiagnosticsFixture';
import { MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE } from '../fixtures/modelCatalogPerformanceFixture';
import {
    MODEL_CATALOG_FIXTURE_MODEL_COUNT,
    MODEL_CATALOG_FIXTURE_RESPONSE,
    MODEL_CATALOG_FIXTURE_ROUTE,
    MODEL_CATALOG_MODALITY_EXPECTATIONS,
    MODEL_CATALOG_PERFORMANCE_FIXTURE_ROUTE,
    MODEL_CATALOG_PERFORMANCE_MODEL_COUNT,
} from '../fixtures/modelCatalogFixture';

interface CatalogSummary {
    modelCount: number;
    modalities: Record<string, string[]>;
    compatible: Record<string, string[]>;
    paid: Record<string, boolean>;
    selection: string;
    allCapabilities: {
        provider: string;
        icon: string;
        pricing: Record<string, string>;
        contextLength: number;
        billingType: string;
        requiresConnection: boolean;
        structured: boolean;
        nativeTools: boolean;
        meridianTools: boolean;
        supportedTools: string[];
        reasoningEfforts: number;
    };
    defaults: {
        provider: string;
        icon: string;
        billingType: string;
        reasoningEfforts: number;
        supportedTools: string[];
        requiresConnection: boolean;
    };
    warnings: Array<Record<string, JsonValue>>;
    unsupportedVersion: { error: string; countBefore: number; countAfter: number };
    malformedRequiredValue: { error: string; countBefore: number; countAfter: number };
    sorting: { nameDescending: string[]; dateDescending: string[] };
}

interface CatalogPerformanceSummary {
    modelCount: number;
    timing: { iterations: number; medianMs: number; p95Ms: number };
}

const routeFixture = async (page: Page, catalog = MODEL_CATALOG_FIXTURE_RESPONSE) => {
    let modelRequestCount = 0;
    await page.route('**/api/models', async (route) => {
        modelRequestCount += 1;
        await route.fulfill({ json: catalog });
    });
    await page.route('**/api/user/settings', (route) => route.fulfill({ json: {} }));
    await page.route('**/api/inference/providers/status', (route) =>
        route.fulfill({
            json: {
                providers: [
                    {
                        provider: 'github_copilot',
                        label: 'GitHub Copilot',
                        isConnected: true,
                        requiresUserToken: false,
                    },
                ],
            },
        }),
    );
    return () => modelRequestCount;
};

const mountFixture = async (page: Page, catalog = MODEL_CATALOG_FIXTURE_RESPONSE) => {
    const requestCount = await routeFixture(page, catalog);
    await page.goto(MODEL_CATALOG_FIXTURE_ROUTE);

    const fixturePage = page.getByTestId('model-catalog-fixture-page');
    await expect(fixturePage).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Model', exact: true })).toHaveValue(
        'Ling-3.0-flash',
    );
    const summary = await page
        .getByTestId('model-catalog-summary')
        .evaluate<CatalogSummary>((element) => JSON.parse(element.textContent ?? '{}'));

    return {
        page,
        fixturePage,
        summary,
        modelRequestCount: requestCount(),
    };
};

const isolatePerformancePage = async (page: Page) => {
    await page.route('**/api/models', (route) => route.fulfill({ json: { version: 1, data: [] } }));
    await page.route('**/api/user/settings', (route) => route.fulfill({ json: {} }));
    await page.route('**/api/inference/providers/status', (route) =>
        route.fulfill({ json: { providers: [] } }),
    );
    await page.route('**/api/auth/github/status', (route) =>
        route.fulfill({ json: { isConnected: false } }),
    );
};

// Compile the client once per worker, outside interaction timing and test timeouts.
// Each test still mounts a fresh selector in a fresh browser context.
const test = diagnosticsTest.extend<Record<string, never>, { catalogBootstrap: true }>({
    catalogBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const context = await browser.newContext();
            const page = await context.newPage();
            const capture = startBrowserDiagnostics(page);
            try {
                await routeFixture(page);
                const baseURL = workerInfo.project.use.baseURL;
                if (!baseURL) throw new Error('Catalog bootstrap requires baseURL');
                await page.goto(new URL(MODEL_CATALOG_FIXTURE_ROUTE, baseURL).toString(), {
                    timeout: 120_000,
                });
                await expect(
                    page.getByRole('combobox', { name: 'Model', exact: true }),
                ).toHaveValue('Ling-3.0-flash', { timeout: 120_000 });
            } catch (error) {
                throw new Error(
                    `Catalog bootstrap failed.\n${formatBrowserDiagnostics(capture.report)}`,
                    { cause: error },
                );
            } finally {
                capture.stop();
                await context.close();
            }
            await use(true);
        },
        { scope: 'worker', auto: true, timeout: 120_000 },
    ],
});

const expectActiveOptionVisible = async (page: Page, input: Locator) => {
    const id = await input.getAttribute('aria-activedescendant');
    expect(id).toBeTruthy();
    const active = page.locator(`[id="${id}"]`);
    await expect(active).toHaveAttribute('role', 'option');
    await expect
        .poll(() =>
            active.evaluate((element) => {
                const list = element.closest('[role="listbox"]');
                if (!list) return false;
                const bounds = element.getBoundingClientRect();
                const viewport = list.getBoundingClientRect();
                return bounds.top >= viewport.top - 1 && bounds.bottom <= viewport.bottom + 1;
            }),
        )
        .toBe(true);
    await expect(input).toBeFocused();
    return active;
};

baseTest('mirrors the frozen version-1 capability and supported-tool bits', () => {
    expect(MODEL_CAPABILITY_BITS).toEqual({
        textOutput: 1,
        imageOutput: 2,
        videoOutput: 4,
        structuredOutputs: 8,
        nativeTools: 16,
        meridianTools: 32,
        subscription: 64,
    });
    expect(MODEL_SUPPORTED_TOOL_BITS).toEqual({
        web_search: 1,
        link_extraction: 2,
        image_generation: 4,
        execute_code: 8,
        visualise: 16,
        ask_user: 32,
    });
});

test('decodes version 1 once at the API boundary and preserves every output combination', async ({
    page,
}) => {
    const { summary, modelRequestCount } = await mountFixture(page);

    expect(modelRequestCount).toBe(1);
    expect(summary.modelCount).toBe(MODEL_CATALOG_FIXTURE_MODEL_COUNT);
    expect(summary.modalities).toEqual(MODEL_CATALOG_MODALITY_EXPECTATIONS);
    expect(summary.modalities['fixture-unknown-bits-only']).toEqual([]);
});

test(
    'preserves store filtering, pricing, selection, sorting, provider, and capability behavior',
    {
        tag: '@smoke',
    },
    async ({ page }) => {
        const { summary } = await mountFixture(page);

        expect(summary.compatible.text).toEqual(['fixture-text', 'fixture-unknown-bits-only']);
        expect(summary.compatible.image).toEqual([
            'fixture-image',
            'fixture-text-image',
            'fixture-image-video',
            'fixture-all-capabilities',
        ]);
        expect(summary.compatible.video).toEqual([
            'fixture-video',
            'fixture-text-video',
            'fixture-image-video',
            'fixture-all-capabilities',
        ]);
        expect(summary.compatible.structured).toEqual(['fixture-all-capabilities']);
        expect(summary.compatible.meridianTools).toEqual(['fixture-all-capabilities']);
        expect(summary.paid).toMatchObject({
            'fixture-text': false,
            'fixture-image': true,
            'fixture-video': true,
            'fixture-text-image': true,
            'fixture-text-video': true,
            'fixture-image-video': false,
            'fixture-all-capabilities': true,
            'fixture-unknown-bits-only': false,
        });
        expect(summary.selection).toBe('fixture-all-capabilities');
        expect(summary.allCapabilities).toEqual({
            provider: 'github_copilot',
            icon: 'github-copilot',
            pricing: { prompt: '0.000003', completion: '0.000006', image: '0.04' },
            contextLength: 128000,
            billingType: 'subscription',
            requiresConnection: true,
            structured: true,
            nativeTools: true,
            meridianTools: true,
            supportedTools: [
                'web_search',
                'link_extraction',
                'image_generation',
                'execute_code',
                'visualise',
                'ask_user',
            ],
            reasoningEfforts: -1,
        });
        expect(summary.sorting.nameDescending[0]).toBe('Zulu All Capabilities');
        expect(summary.sorting.dateDescending.slice(0, 2)).toEqual([
            'fixture-all-capabilities',
            'fixture-text',
        ]);
    },
);

test('applies optional defaults, retains warnings, and rejects invalid catalogs before store update', async ({
    page,
}) => {
    const { summary } = await mountFixture(page);

    expect(summary.defaults).toEqual({
        provider: 'openrouter',
        icon: '',
        billingType: 'metered',
        reasoningEfforts: 0,
        supportedTools: [],
        requiresConnection: false,
    });
    expect(summary.warnings).toEqual(MODEL_CATALOG_FIXTURE_RESPONSE.warnings);
    const warningAlert = page.getByRole('alert');
    await expect(warningAlert).toHaveCount(1);
    await expect(warningAlert.getByText('Fixture provider warning', { exact: true })).toBeVisible();
    await expect(
        warningAlert.getByText('Reconnect the fixture provider to refresh its catalog.', {
            exact: true,
        }),
    ).toBeVisible();
    await expect(
        warningAlert.getByRole('button', { name: 'Reconnect', exact: true }),
    ).toBeVisible();

    expect(summary.unsupportedVersion.error).toContain('Unsupported model catalog version: 2');
    expect(summary.unsupportedVersion.countAfter).toBe(summary.unsupportedVersion.countBefore);
    expect(summary.malformedRequiredValue.error).toContain('data[0].name');
    expect(summary.malformedRequiredValue.countAfter).toBe(
        summary.malformedRequiredValue.countBefore,
    );
});

test('keeps filtered model rows consecutive after activation and scrolling', async ({ page }) => {
    await mountFixture(page);

    const selector = page.getByTestId('model-selector-spacing-fixture');
    const input = selector.locator('input');
    await input.click();

    const panel = page.locator('.ui-models-panel');
    await expect(panel).toBeVisible();
    const list = panel.locator('.custom_scroll');
    const lingOption = panel.getByRole('option', { name: /Ling-3\.0-flash/ });
    const githubJump = panel.getByRole('button', { name: /GitHub Copilot 1/ });

    await expect
        .poll(() =>
            panel.evaluate((element) => {
                const transform = new DOMMatrixReadOnly(window.getComputedStyle(element).transform);
                return transform.a;
            }),
        )
        .toBeCloseTo(0.8, 2);

    await githubJump.click();
    await expect(
        panel.getByRole('option', { name: /GitHub Copilot.*GitHub Subscription Text/ }),
    ).toBeVisible();

    for (let iteration = 0; iteration < 3; iteration += 1) {
        await input.fill('Flash');
        await input.fill('Laguna XS 2.1');
    }
    const duplicateIdOptions = panel.getByRole('option', { name: /Poolside: Laguna XS 2\.1/ });
    await expect(duplicateIdOptions).toHaveCount(2);
    const duplicateGeometry = await duplicateIdOptions.evaluateAll((elements) =>
        elements.map((element) => {
            const bounds = element.getBoundingClientRect();
            return {
                id: element.id,
                rowIndex: element.getAttribute('data-model-row-index'),
                top: bounds.top,
                bottom: bounds.bottom,
            };
        }),
    );
    expect(new Set(duplicateGeometry.map((row) => row.id)).size).toBe(2);
    expect(new Set(duplicateGeometry.map((row) => row.rowIndex)).size).toBe(2);
    const orderedDuplicateRows = duplicateGeometry.toSorted((left, right) => left.top - right.top);
    expect(orderedDuplicateRows[1].top).toBeGreaterThanOrEqual(
        orderedDuplicateRows[0].bottom - 1,
    );

    await input.fill('Flash');
    await expect(lingOption).toBeVisible();
    await expect(lingOption).toHaveAttribute('aria-selected', 'true');
    await input.press('ArrowDown');
    await input.press('ArrowDown');

    await list.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
        element.dispatchEvent(new Event('scroll'));
    });
    await expect(
        panel.getByRole('option', { name: /OpenRouter: Long Context Flash/ }),
    ).toBeVisible();
    await input.press('ArrowUp');

    await input.fill('Gemini');
    await expect(panel.getByRole('option', { name: /Gemini 3\.6 Flash/ })).toBeVisible();
    await input.fill('Flash');
    await expect(lingOption).toBeVisible();

    for (let index = 0; index < 8; index += 1) {
        await input.press('ArrowDown');
    }

    const activeOptionId = await input.getAttribute('aria-activedescendant');
    expect(activeOptionId).not.toBeNull();
    await expect(panel.locator(`#${activeOptionId}`)).toBeVisible();

    await list.evaluate((element) => {
        element.scrollTop = Math.min(180, element.scrollHeight - element.clientHeight);
        element.dispatchEvent(new Event('scroll'));
    });

    const geometry = await panel.getByRole('option').evaluateAll((elements) => {
        const listElement = elements[0]?.closest('.custom_scroll');
        if (!(listElement instanceof HTMLElement)) {
            throw new TypeError('Model options are missing their scrolling container');
        }

        const viewport = listElement.getBoundingClientRect();
        const rows = elements
            .map((element) => {
                const bounds = element.getBoundingClientRect();
                return {
                    name: element.getAttribute('title') ?? element.textContent ?? '',
                    top: bounds.top,
                    bottom: bounds.bottom,
                    visibility: window.getComputedStyle(element).visibility,
                };
            })
            .filter(
                (row) =>
                    row.visibility !== 'hidden' &&
                    row.bottom > viewport.top &&
                    row.top < viewport.bottom,
            );
        const errors = rows.slice(1).map((row, index) => Math.abs(row.top - rows[index].bottom));

        return {
            rows,
            maxError: errors.length ? Math.max(...errors) : Number.POSITIVE_INFINITY,
            scrollTop: listElement.scrollTop,
            scrollHeight: listElement.scrollHeight,
        };
    });

    expect(geometry.rows.length).toBeGreaterThanOrEqual(3);
    expect(geometry.maxError, JSON.stringify(geometry, null, 2)).toBeLessThanOrEqual(2);
});

test(
    'decodes 500 models within the browser timing budget after warm-up',
    {
        tag: '@performance',
    },
    async ({ page }) => {
        await isolatePerformancePage(page);
        await page.goto(MODEL_CATALOG_PERFORMANCE_FIXTURE_ROUTE);
        await expect(page.getByTestId('model-catalog-performance-fixture-page')).toBeVisible();
        const summaryElement = page.getByTestId('model-catalog-performance-summary');
        await expect(summaryElement).toBeVisible();
        const summary = await summaryElement.evaluate<CatalogPerformanceSummary>((element) =>
            JSON.parse(element.textContent ?? '{}'),
        );

        expect(summary.modelCount).toBe(MODEL_CATALOG_PERFORMANCE_MODEL_COUNT);
        expect(summary.timing.iterations).toBe(50);
        expect(summary.timing.medianMs).toBeLessThanOrEqual(10);
        expect(summary.timing.p95Ms).toBeLessThanOrEqual(20);
    },
);

test(
    'bounds 500-model option mounts and navigates the entire catalog accessibly',
    { tag: '@smoke' },
    async ({ page }) => {
        const { summary } = await mountFixture(page, MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE);
        expect(summary.modelCount).toBe(500);
        const input = page.getByRole('combobox', { name: 'Model', exact: true });
        const panel = page.locator('.ui-models-panel');
        const options = panel.getByRole('option');
        await expect(options).toHaveCount(0);
        await input.click();
        await expect(panel).toBeVisible();
        await expect(input).toHaveAttribute('aria-expanded', 'true');
        await expect(options.first()).toHaveAttribute('aria-setsize', '494');
        expect(await options.count()).toBeLessThanOrEqual(20);
        await expectActiveOptionVisible(page, input);

        // Cross many virtual windows with real keyboard events, not just End/scroll.
        for (let index = 0; index < 80; index += 1) await input.press('ArrowDown');
        let active = await expectActiveOptionVisible(page, input);
        expect(Number(await active.getAttribute('aria-posinset'))).toBeGreaterThan(80);
        expect(await options.count()).toBeLessThanOrEqual(20);
        await input.press('End');
        active = await expectActiveOptionVisible(page, input);
        await expect(active).toHaveAttribute('aria-posinset', '494');
        await input.press('ArrowUp');
        active = await expectActiveOptionVisible(page, input);
        await expect(active).toHaveAttribute('aria-posinset', '493');
        const selectedName = await active.getAttribute('title');
        await input.press('Enter');
        await expect(panel).toHaveCount(0);
        await expect(input).toHaveValue(selectedName!);
        await expect(input).toBeFocused();

        await input.press('ArrowDown');
        active = await expectActiveOptionVisible(page, input);
        await expect(active).toHaveAttribute('aria-selected', 'true');
        await expect(active).toHaveAttribute('aria-posinset', '493');
        await input.fill('Generated Model 450');
        await expect(options).toHaveCount(1);
        await expect(options.first()).toHaveAttribute('aria-setsize', '1');
        await input.press('Control+Shift+P');
        await expect(options).toHaveCount(2);
        await expect(options.filter({ hasText: 'Pinned' })).toHaveCount(1);
        await input.press('Meta+Shift+P');
        await expect(options).toHaveCount(1);
        await options.first().click();
        await expect(input).toHaveValue('Generated Model 450');
        await expect(panel).toHaveCount(0);

        await input.click();
        await input.fill('no matching model');
        await expect(options).toHaveCount(0);
        await expect(input).not.toHaveAttribute('aria-activedescendant');
        await expect(panel.getByRole('status')).toContainText('No models match');
        await input.press('Escape');
        await expect(panel).toHaveCount(0);
        await expect(input).toHaveValue('Generated Model 450');
        await expect(input).toHaveAttribute('aria-expanded', 'false');
        await expect(input).toBeFocused();
        await input.click();
        await panel.getByRole('button', { name: /GitHub Copilot 1/ }).click();
        active = await expectActiveOptionVisible(page, input);
        await expect(active).toContainText('GitHub Subscription Text');
        expect(await options.count()).toBeLessThanOrEqual(20);

        // Wheel away without leaving a dangling aria-activedescendant.
        await panel.getByRole('listbox').evaluate((element) => {
            element.scrollTop = element.scrollHeight / 2;
            element.dispatchEvent(new Event('scroll'));
        });
        await expect(active).toHaveCount(1);
        expect(await options.count()).toBeLessThanOrEqual(20);
        await input.press('ArrowDown');
        await expectActiveOptionVisible(page, input);
        await page.getByRole('heading', { name: 'Model catalog fixture' }).click();
        await expect(panel).toHaveCount(0);
        await expect(input).toHaveAttribute('aria-expanded', 'false');

        await input.click();
        await input.fill('Generated Model 451');
        await input.press('Tab');
        await expect(panel).toHaveCount(0);
        await expect(input).toHaveValue('Generated Model 451');
        await expect(input).not.toBeFocused();

        await input.click();
        await input.press('Home');
        active = await expectActiveOptionVisible(page, input);
        await expect(active).toHaveAttribute('aria-posinset', '1');
        await input.press('Escape');
    },
);

test(
    'opens a fresh 500-model selector within the responsiveness budget',
    { tag: '@performance' },
    async ({ page }) => {
        await mountFixture(page, MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE);
        const input = page.getByRole('combobox', { name: 'Model', exact: true });
        const samples = [];
        for (let iteration = 0; iteration < 3; iteration += 1) {
            const sample = await input.evaluate(async (element) => {
                const longTasks: number[] = [];
                let mountedOptions = 0;
                const mutations = new MutationObserver((records) => {
                    for (const record of records) {
                        for (const node of record.addedNodes) {
                            if (!(node instanceof Element)) continue;
                            mountedOptions += Number(node.matches('[role="option"]'));
                            mountedOptions += node.querySelectorAll('[role="option"]').length;
                        }
                    }
                });
                mutations.observe(document.body, { childList: true, subtree: true });
                const observer = new PerformanceObserver((entries) => {
                    longTasks.push(...entries.getEntries().map((entry) => entry.duration));
                });
                observer.observe({ type: 'longtask' });
                const start = performance.now();
                if (!(element instanceof HTMLInputElement)) throw new Error('Expected model input');
                element.click();
                await new Promise<void>((resolve) =>
                    requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
                );
                const panel = document.querySelector('.ui-models-panel');
                const options = panel?.querySelectorAll('[role="option"]');
                const result = {
                    elapsedMs: performance.now() - start,
                    rendered: options?.length ?? 0,
                    visible: !!panel?.getBoundingClientRect().height && !!options?.length,
                    longestTaskMs: Math.max(0, ...longTasks),
                    mountedOptions,
                };
                observer.disconnect();
                mutations.disconnect();
                return result;
            });
            samples.push(sample);
            expect(sample.visible).toBe(true);
            expect(sample.rendered).toBeLessThanOrEqual(20);
            expect(sample.mountedOptions).toBeLessThanOrEqual(30);
            // Structural bound is the primary guard; generous timing allows CI variance.
            expect(sample.elapsedMs).toBeLessThanOrEqual(300);
            expect(sample.longestTaskMs).toBeLessThanOrEqual(200);
            await input.press('Escape');
            await expect(page.locator('.ui-models-panel')).toHaveCount(0);
        }
        console.info('500-model selector open samples:', JSON.stringify(samples));
    },
);
