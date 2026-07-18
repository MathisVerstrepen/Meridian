import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { MODEL_CAPABILITY_BITS, MODEL_SUPPORTED_TOOL_BITS } from '../../app/types/modelCatalog';
import {
    MODEL_CATALOG_FIXTURE_MODEL_COUNT,
    MODEL_CATALOG_FIXTURE_RESPONSE,
    MODEL_CATALOG_FIXTURE_ROUTE,
    MODEL_CATALOG_MODALITY_EXPECTATIONS,
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
    warnings: Array<Record<string, unknown>>;
    unsupportedVersion: { error: string; countBefore: number; countAfter: number };
    malformedRequiredValue: { error: string; countBefore: number; countAfter: number };
    timing: { iterations: number; medianMs: number; p95Ms: number };
    sorting: { nameDescending: string[]; dateDescending: string[] };
}

const mountFixture = async (page: Page) => {
    let modelRequestCount = 0;
    await page.route('**/api/models', async (route) => {
        modelRequestCount += 1;
        await route.fulfill({ json: MODEL_CATALOG_FIXTURE_RESPONSE });
    });
    await page.goto(MODEL_CATALOG_FIXTURE_ROUTE);

    const fixturePage = page.getByTestId('model-catalog-fixture-page');
    await expect(fixturePage).toBeVisible();
    const summaryText = await page.getByTestId('model-catalog-summary').textContent();
    expect(summaryText).not.toBeNull();

    return {
        page,
        fixturePage,
        summary: JSON.parse(summaryText ?? '{}') as CatalogSummary,
        modelRequestCount,
    };
};

test('mirrors the frozen version-1 capability and supported-tool bits', () => {
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

test('preserves store filtering, pricing, selection, sorting, provider, and capability behavior', {
    tag: '@smoke',
}, async ({ page }) => {
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
});

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
    await expect(warningAlert.getByRole('button', { name: 'Reconnect', exact: true })).toBeVisible();

    expect(summary.unsupportedVersion.error).toContain('Unsupported model catalog version: 2');
    expect(summary.unsupportedVersion.countAfter).toBe(summary.unsupportedVersion.countBefore);
    expect(summary.malformedRequiredValue.error).toContain('data[0].name');
    expect(summary.malformedRequiredValue.countAfter).toBe(
        summary.malformedRequiredValue.countBefore,
    );
});

test('decodes 500 models within the browser timing budget after warm-up', async ({ page }) => {
    const { summary } = await mountFixture(page);

    expect(summary.timing.iterations).toBe(50);
    expect(summary.timing.medianMs).toBeLessThanOrEqual(10);
    expect(summary.timing.p95Ms).toBeLessThanOrEqual(20);
});
