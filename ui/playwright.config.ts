import { defineConfig, devices } from '@playwright/test';
import { GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE } from './e2e/fixtures/markdownRendererGoldenCase';

export default defineConfig({
    testDir: './e2e/tests',
    fullyParallel: false,
    workers: 1,
    timeout: 30_000,
    expect: {
        timeout: 10_000,
    },
    use: {
        baseURL: 'http://127.0.0.1:4173',
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
        command: 'pnpm exec nuxt dev --host 127.0.0.1 --port 4173',
        url: `http://127.0.0.1:4173${GOLDEN_MARKDOWN_RENDERER_FIXTURE_ROUTE}`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
});
