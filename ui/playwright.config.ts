import { defineConfig, devices } from '@playwright/test';
import { GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE } from './e2e/fixtures/markdownRendererGoldenCase';

const playwrightServerPort = process.env.MARKDOWN_RENDERER_PLAYWRIGHT_PORT ?? '4173';
const playwrightBaseUrl = `http://127.0.0.1:${playwrightServerPort}`;
const graphResponseMockPort = process.env.GRAPH_RESPONSE_MOCK_PORT ?? '4174';
const graphResponseMockUrl = `http://127.0.0.1:${graphResponseMockPort}`;

export default defineConfig({
    testDir: './e2e/tests',
    fullyParallel: false,
    workers: 1,
    timeout: 30_000,
    expect: {
        timeout: 10_000,
    },
    use: {
        baseURL: playwrightBaseUrl,
        trace: 'on-first-retry',
    },
    projects: [
        {
            name: 'chromium',
            use: {
                ...devices['Desktop Chrome'],
            },
        },
    ],
    webServer: [
        {
            command: 'node e2e/scripts/graphResponseApiMock.mjs',
            url: `${graphResponseMockUrl}/__health`,
            env: { GRAPH_RESPONSE_MOCK_PORT: graphResponseMockPort },
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
        },
        {
            command: `pnpm exec nuxt dev --host 127.0.0.1 --port ${playwrightServerPort}`,
            url: `${playwrightBaseUrl}${GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE}`,
            env: { NUXT_API_INTERNAL_BASE_URL: graphResponseMockUrl },
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
        },
    ],
});
