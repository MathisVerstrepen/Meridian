import { createHash } from 'node:crypto';
import { expect, test } from '@playwright/test';
import type { BrowserContext, Page } from '@playwright/test';
import {
    GRAPH_RESPONSE_EDGE_COUNT,
    GRAPH_RESPONSE_FIXTURE_ROUTE,
    GRAPH_RESPONSE_FIXTURE_TOKEN,
    GRAPH_RESPONSE_IDS,
    GRAPH_RESPONSE_MOCK_PORT,
    GRAPH_RESPONSE_NODE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_FIXTURE_ROUTE,
    GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH,
    GRAPH_RESPONSE_REPLY,
    GRAPH_RESPONSE_REPLY_LENGTH,
} from '../fixtures/graphResponseFixture';

interface GraphResponseSummary {
    graph: Record<string, unknown>;
    counts: {
        nodes: number;
        edges: number;
        expectedNodes: number;
        expectedEdges: number;
    };
    node: Record<string, unknown>;
    edge: Record<string, unknown>;
    reply: { length: number; hash: string; startsWith: string; endsWith: string };
    opaqueDataPreservedByReference: boolean;
    outbound: { nodeGraphId: string; edgeGraphId: string };
    unsupported: { error: string; countBefore: number; countAfter: number };
    malformed: { error: string; countBefore: number; countAfter: number };
    gzip: { nodes: number; replyLength: number };
}

interface GraphResponsePerformanceSummary {
    nodes: number;
    edges: number;
    replyLength: number;
    timing: { iterations: number; payloadBytes: number; medianMs: number; p95Ms: number };
}

const addAuthCookie = (context: BrowserContext) =>
    context.addCookies([
        {
            name: 'auth_token',
            value: GRAPH_RESPONSE_FIXTURE_TOKEN,
            url: `http://127.0.0.1:${process.env.MARKDOWN_RENDERER_PLAYWRIGHT_PORT ?? '4173'}`,
            httpOnly: true,
        },
    ]);

const mountFixture = async (page: Page): Promise<GraphResponseSummary> => {
    await addAuthCookie(page.context());
    await page.goto(GRAPH_RESPONSE_FIXTURE_ROUTE);
    await expect(page.getByTestId('graph-response-fixture-page')).toBeVisible();
    await expect(page.getByTestId('graph-response-summary')).toBeVisible({ timeout: 30_000 });
    const text = await page.getByTestId('graph-response-summary').textContent();
    expect(text).not.toBeNull();
    return JSON.parse(text ?? '{}') as GraphResponseSummary;
};

const mockRequestCounts = async (): Promise<Record<string, number>> => {
    const response = await fetch(
        `http://127.0.0.1:${process.env.GRAPH_RESPONSE_MOCK_PORT ?? GRAPH_RESPONSE_MOCK_PORT}/__requests`,
    );
    return (await response.json()) as Record<string, number>;
};

const isolatePerformancePage = async (page: Page) => {
    await page.route('**/api/models', (route) =>
        route.fulfill({ json: { version: 1, data: [] } }),
    );
    await page.route('**/api/user/settings', (route) => route.fulfill({ json: {} }));
    await page.route('**/api/inference/providers/status', (route) =>
        route.fulfill({ json: { providers: [] } }),
    );
    await page.route('**/api/auth/github/status', (route) =>
        route.fulfill({ json: { isConnected: false } }),
    );
};

test('Nitro blocks a missing auth cookie before the graph upstream', async ({ request }) => {
    const path = `/graph/${GRAPH_RESPONSE_IDS.valid}`;
    const before = await mockRequestCounts();
    const response = await request.get(`/api${path}`);
    const after = await mockRequestCounts();

    expect(response.status()).toBe(401);
    expect(after[path] ?? 0).toBe(before[path] ?? 0);
});

test('proxies auth/path, decodes v1 once, restores defaults, maps, and preserves replies', {
    tag: '@smoke',
}, async ({ page }) => {
    test.setTimeout(60_000);
    const summary = await mountFixture(page);

    expect(summary.graph).toEqual({
        id: GRAPH_RESPONSE_IDS.valid,
        name: 'Large graph response fixture',
        node_count: GRAPH_RESPONSE_NODE_COUNT,
        folder_id: null,
        workspace_id: null,
        description: null,
        temporary: false,
        pinned: false,
        created_at: null,
        updated_at: null,
        custom_instructions: [],
        max_tokens: null,
        temperature: null,
        top_p: null,
        top_k: null,
        frequency_penalty: null,
        presence_penalty: null,
        repetition_penalty: null,
        reasoning_effort: null,
    });
    expect(summary.counts).toEqual({
        nodes: GRAPH_RESPONSE_NODE_COUNT,
        edges: GRAPH_RESPONSE_EDGE_COUNT,
        expectedNodes: GRAPH_RESPONSE_NODE_COUNT,
        expectedEdges: GRAPH_RESPONSE_EDGE_COUNT,
    });
    expect(summary.node).toMatchObject({
        id: 'node-0',
        position: { x: 12.5, y: -7.25 },
        style: { width: '100px', height: '100px' },
        parentNode: null,
        promptStyle: { width: '240px', height: '160px' },
        promptParentNode: 'node-0',
        promptData: {
            prompt: 'Fixture prompt',
            templateId: 'template-1',
            templateVariables: {},
        },
    });
    expect(summary.edge).toEqual({
        source: 'node-0',
        target: 'node-1',
        sourceHandle: 'context_output',
        targetHandle: 'prompt_input',
        label: 'Fixture edge',
        type: 'customEdge',
        animated: true,
        style: { stroke: '#ff7a1a', strokeWidth: 2 },
        data: { weight: 0, enabled: false, tags: [] },
        defaultAnimated: false,
    });

    expect(summary.reply.length).toBe(GRAPH_RESPONSE_REPLY_LENGTH);
    expect(summary.reply.hash).toBe(createHash('sha256').update(GRAPH_RESPONSE_REPLY).digest('hex'));
    expect(summary.reply.startsWith).toBe(GRAPH_RESPONSE_REPLY.slice(0, 48));
    expect(summary.reply.endsWith).toBe(GRAPH_RESPONSE_REPLY.slice(-48));
    expect(summary.opaqueDataPreservedByReference).toBe(true);
    expect(summary.outbound).toEqual({
        nodeGraphId: GRAPH_RESPONSE_IDS.valid,
        edgeGraphId: GRAPH_RESPONSE_IDS.valid,
    });
    expect(summary.gzip).toEqual({
        nodes: GRAPH_RESPONSE_NODE_COUNT,
        replyLength: GRAPH_RESPONSE_REPLY_LENGTH,
    });

    expect(summary.unsupported.error).toContain('Unsupported graph response version: 2');
    expect(summary.unsupported.countAfter).toBe(summary.unsupported.countBefore);
    expect(summary.malformed.error).toContain('nodes[0].position_x');
    expect(summary.malformed.countAfter).toBe(summary.malformed.countBefore);

});

test('observes upstream gzip decoding through the real Nitro proxy', async ({ context }) => {
    await addAuthCookie(context);
    const response = await context.request.get(`/api/graph/${GRAPH_RESPONSE_IDS.gzip}`);

    expect(response.ok()).toBe(true);
    expect(response.headers()['x-fixture-upstream-encoding']).toBe('gzip');
    expect(response.headers()['content-encoding']).toBeUndefined();
    expect(response.headers()['content-length']).not.toBe(
        response.headers()['x-fixture-upstream-length'],
    );
    const value = (await response.json()) as { version: number; nodes: unknown[]; edges: unknown[] };
    expect(value.version).toBe(1);
    expect(value.nodes).toHaveLength(GRAPH_RESPONSE_NODE_COUNT);
    expect(value.edges).toHaveLength(GRAPH_RESPONSE_EDGE_COUNT);
});

test('decodes and maps 500 nodes within the browser timing budget after warm-up', {
    tag: '@performance',
}, async ({ page }) => {
    test.setTimeout(60_000);
    await isolatePerformancePage(page);
    await page.goto(GRAPH_RESPONSE_PERFORMANCE_FIXTURE_ROUTE);
    await expect(page.getByTestId('graph-response-performance-fixture-page')).toBeVisible();
    const summaryElement = page.getByTestId('graph-response-performance-summary');
    await expect(summaryElement).toBeVisible({ timeout: 30_000 });
    const text = await summaryElement.textContent();
    expect(text).not.toBeNull();
    const summary = JSON.parse(text ?? '{}') as GraphResponsePerformanceSummary;

    expect(summary.nodes).toBe(GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT);
    expect(summary.edges).toBe(GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT);
    expect(summary.replyLength).toBe(GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH);
    expect(summary.timing.iterations).toBe(30);
    expect(summary.timing.payloadBytes).toBeGreaterThan(4_000_000);
    expect(summary.timing.payloadBytes).toBeLessThan(5_500_000);
    expect(summary.timing.medianMs).toBeLessThanOrEqual(20);
    expect(summary.timing.p95Ms).toBeLessThanOrEqual(40);
});
