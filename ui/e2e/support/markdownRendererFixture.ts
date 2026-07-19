import type { Locator, Page } from '@playwright/test';
import {
    DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY,
    GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE,
    MARKDOWN_RENDERER_FIXTURE_CASES,
    ONE_PIXEL_PNG_BASE64,
    type MarkdownRendererFixtureCase,
} from '../fixtures/markdownRendererGoldenCase';
import {
    expect as baseExpect,
    formatBrowserDiagnostics,
    startBrowserDiagnostics,
    test as diagnosticsTest,
} from './browserDiagnosticsFixture';

const COLD_BOOTSTRAP_TIMEOUT = 120_000;

interface MarkdownRendererWorkerFixtures {
    markdownRendererBootstrap: true;
}

const resolveMarkdownRendererFixtureCase = (caseKey: string): MarkdownRendererFixtureCase => {
    const fixtureCase = MARKDOWN_RENDERER_FIXTURE_CASES[caseKey];
    if (!fixtureCase) {
        throw new Error(`Unknown markdown renderer fixture case: ${caseKey}`);
    }
    return fixtureCase;
};

const installMarkdownRendererFixtureRoutes = (
    page: Page,
    fixtureCase: MarkdownRendererFixtureCase,
): Promise<void> => page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const toolCallId = url.pathname.match(/^\/api\/chat\/tool-call\/(.+)$/)?.[1];

    if (toolCallId && fixtureCase.toolCallDetails?.[toolCallId]) {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(fixtureCase.toolCallDetails[toolCallId]),
        });
        return;
    }

    const imageId = url.pathname.match(/^\/api\/auth\/refresh\/files\/view\/(.+)$/)?.[1];
    if (imageId && fixtureCase.generatedImageIds?.includes(imageId)) {
        await route.fulfill({
            status: 200,
            contentType: 'image/png',
            body: Buffer.from(ONE_PIXEL_PNG_BASE64, 'base64'),
        });
        return;
    }

    const embedId = url.pathname.match(/^\/api\/files\/embed\/(.+)$/)?.[1];
    if (embedId && fixtureCase.embeddedArtifactIds?.includes(embedId)) {
        await route.fulfill({
            status: 200,
            contentType: 'text/html',
            body: '<!doctype html><html><body>Embedded fixture</body></html>',
        });
        return;
    }

    await route.abort('failed');
    throw new Error(`Unexpected API request during markdown renderer fixture test: ${url.pathname}`);
});

export const expect = baseExpect;
export const test = diagnosticsTest.extend<Record<string, never>, MarkdownRendererWorkerFixtures>({
    markdownRendererBootstrap: [
        async ({ browser }, use, workerInfo) => {
            const context = await browser.newContext();
            const page = await context.newPage();
            const diagnosticsCapture = startBrowserDiagnostics(page);

            try {
                const baseURL = workerInfo.project.use.baseURL;
                if (typeof baseURL !== 'string') {
                    throw new Error('Markdown renderer bootstrap requires a configured baseURL');
                }
                const fixtureCase = resolveMarkdownRendererFixtureCase(
                    DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY,
                );
                await installMarkdownRendererFixtureRoutes(page, fixtureCase);
                await page.goto(new URL(GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE, baseURL).toString(), {
                    timeout: COLD_BOOTSTRAP_TIMEOUT,
                });
                await baseExpect(page.getByTestId('markdown-renderer-fixture-page')).toHaveAttribute(
                    'data-rendered',
                    'true',
                    { timeout: COLD_BOOTSTRAP_TIMEOUT },
                );
            } catch (error) {
                const diagnostics = formatBrowserDiagnostics(diagnosticsCapture.report);
                throw new Error(`Markdown renderer cold bootstrap failed.\n\n${diagnostics}`, {
                    cause: error,
                });
            } finally {
                diagnosticsCapture.stop();
                await context.close();
            }

            await use(true);
        },
        { scope: 'worker', auto: true, timeout: COLD_BOOTSTRAP_TIMEOUT },
    ],
});

export type MarkdownRendererPerfRun = {
    nodeId: string | null;
    parseId: number;
    markdownLength: number;
    isStreaming: boolean;
    status: 'completed' | 'empty' | 'stale';
    measures: Partial<Record<MarkdownRendererPerfPhaseName, number>>;
    startedAt: number;
    completedAt: number;
};

export type MarkdownRendererPerfPhaseName =
    | 'preprocessMs'
    | 'markdownProcessorMs'
    | 'domEnhancementMs'
    | 'mermaidMs'
    | 'totalMs';

export const mountMarkdownRendererFixture = async (page: Page, caseKey: string) => {
    const fixtureCase = resolveMarkdownRendererFixtureCase(caseKey);
    await installMarkdownRendererFixtureRoutes(page, fixtureCase);

    const suffix =
        caseKey === DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY ? '' : `?case=${encodeURIComponent(caseKey)}`;
    await page.goto(`${GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE}${suffix}`);

    const fixturePage = page.getByTestId('markdown-renderer-fixture-page');
    await expect(fixturePage).toHaveAttribute('data-rendered', 'true');
    await expect(fixturePage).toHaveAttribute('data-case-key', fixtureCase.key);

    return {
        fixturePage,
        responseContainer: page.getByTestId('markdown-renderer-response'),
        toolActivities: page.getByTestId('markdown-renderer-tool-activities'),
        thinkingButton: page.getByTestId('thinking-disclosure-button'),
        thinkingPanel: page.getByTestId('thinking-disclosure-panel'),
    };
};

export const expectNoRawMarkers = async (
    responseContainer: Locator,
    markers: string[],
) => {
    const responseHtml = await responseContainer.innerHTML();

    for (const marker of markers) {
        expect(responseHtml).not.toContain(marker);
    }
};

export const getLatestMarkdownRendererPerfRun = async (
    page: Page,
): Promise<MarkdownRendererPerfRun> => {
    await page.waitForFunction(() => {
        const perfStore = (window as typeof window & {
            __markdownRendererPerf?: {
                lastRun?: {
                    measures?: {
                        totalMs?: number;
                    };
                };
            };
        }).__markdownRendererPerf;

        return Boolean(perfStore?.lastRun?.measures?.totalMs);
    });

    const perfRun = await page.evaluate(() => {
        const perfStore = (window as typeof window & {
            __markdownRendererPerf?: {
                lastRun?: MarkdownRendererPerfRun;
            };
        }).__markdownRendererPerf;

        return perfStore?.lastRun ?? null;
    });

    if (!perfRun) {
        throw new Error('No markdown renderer performance run found on the page');
    }

    return perfRun;
};
