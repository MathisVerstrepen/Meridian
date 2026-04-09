import { defineConfig, devices } from '@playwright/test';
import { GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE } from './e2e/fixtures/markdownRendererGoldenCase';

const playwrightServerPort = process.env.MARKDOWN_RENDERER_PLAYWRIGHT_PORT ?? '4173';
const playwrightBaseUrl = `http://127.0.0.1:${playwrightServerPort}`;

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
    webServer: {
        command: `pnpm exec nuxt dev --host 127.0.0.1 --port ${playwrightServerPort}`,
        url: `${playwrightBaseUrl}${GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE}`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
});
