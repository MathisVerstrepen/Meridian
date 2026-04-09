import { spawn } from 'node:child_process';
import process from 'node:process';
import { chromium } from '@playwright/test';

const PORT = 4174;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const FIXTURE_ROUTE = '/auth/markdown-renderer-fixture';
const DEFAULT_ITERATIONS = 12;
const ONE_PIXEL_PNG_BASE64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5WZyQAAAAASUVORK5CYII=';

const GOLDEN_TOOL_CALL_ID = '3e78ca51-189e-492e-b718-d66bd6f97539';
const GOLDEN_IMAGE_ID = 'f62a6a02-7eea-4724-8a2a-b7b1639e8b6e';
const UNCLOSED_THINKING_TOOL_CALL_ID = '0f7d9c9a-0ba0-4efe-b75b-a053eca08634';

const CASES = [
    {
        key: 'golden',
        toolCallDetails: {
            [GOLDEN_TOOL_CALL_ID]: {
                id: GOLDEN_TOOL_CALL_ID,
                node_id: 'fixture-node',
                model_id: 'fixture-model',
                tool_call_id: GOLDEN_TOOL_CALL_ID,
                tool_name: 'ask_user',
                status: 'pending_user_input',
                arguments: {
                    title: '3 questions',
                    questions: [
                        {
                            id: 'subject',
                            question: 'What would you like to see in the image?',
                            input_type: 'text',
                            validation: {
                                placeholder: 'Describe the image subject',
                            },
                        },
                        {
                            id: 'style',
                            question: 'Which art style should I use?',
                            input_type: 'single_select',
                            options: [
                                {
                                    label: '3D isometric',
                                    value: 'isometric',
                                },
                                {
                                    label: 'Pixel art',
                                    value: 'pixel',
                                },
                            ],
                        },
                        {
                            id: 'aspect_ratio',
                            question: 'Which aspect ratio should I use?',
                            input_type: 'single_select',
                            options: [
                                {
                                    label: '1:1',
                                    value: '1:1',
                                },
                                {
                                    label: '16:9',
                                    value: '16:9',
                                },
                            ],
                        },
                    ],
                },
                result: {},
                model_context_payload: '',
                created_at: null,
            },
        },
        generatedImageIds: [GOLDEN_IMAGE_ID],
    },
    {
        key: 'unclosedThinkingWithToolQuestion',
        toolCallDetails: {
            [UNCLOSED_THINKING_TOOL_CALL_ID]: {
                id: UNCLOSED_THINKING_TOOL_CALL_ID,
                node_id: 'fixture-node-unclosed-thinking',
                model_id: 'fixture-model',
                tool_call_id: UNCLOSED_THINKING_TOOL_CALL_ID,
                tool_name: 'ask_user',
                status: 'pending_user_input',
                arguments: {
                    title: '2 follow-ups',
                    questions: [
                        {
                            id: 'medium',
                            question: 'Which medium should the graphic use?',
                            input_type: 'single_select',
                            options: [
                                {
                                    label: 'Poster',
                                    value: 'poster',
                                },
                                {
                                    label: 'Social card',
                                    value: 'social_card',
                                },
                            ],
                        },
                        {
                            id: 'audience',
                            question: 'Who is the target audience?',
                            input_type: 'text',
                            validation: {
                                placeholder: 'Describe the audience',
                            },
                        },
                    ],
                },
                result: {},
                model_context_payload: '',
                created_at: null,
            },
        },
        generatedImageIds: [],
    },
    {
        key: 'streamingImageGeneration',
        toolCallDetails: {},
        generatedImageIds: [],
    },
    {
        key: 'malformedToolAndPlainMarkdownImage',
        toolCallDetails: {},
        generatedImageIds: [],
    },
    {
        key: 'heavyStreaming',
        toolCallDetails: {},
        generatedImageIds: [],
    },
];

const PHASES = [
    'preprocessMs',
    'markdownProcessorMs',
    'domEnhancementMs',
    'mermaidMs',
    'totalMs',
];

const delay = (ms) => new Promise((resolve) => {
    setTimeout(resolve, ms);
});

const toSortedNumbers = (values) => {
    return values
        .filter((value) => typeof value === 'number' && Number.isFinite(value))
        .sort((left, right) => left - right);
};

const percentile = (values, ratio) => {
    if (!values.length) {
        return null;
    }

    const index = Math.max(0, Math.ceil(values.length * ratio) - 1);
    return values[index] ?? null;
};

const median = (values) => {
    if (!values.length) {
        return null;
    }

    const middle = Math.floor(values.length / 2);
    if (values.length % 2 === 0) {
        return Number(((values[middle - 1] + values[middle]) / 2).toFixed(3));
    }

    return Number(values[middle].toFixed(3));
};

const spawnNuxtServer = () => {
    const child = spawn(
        'pnpm',
        ['exec', 'nuxt', 'dev', '--host', '127.0.0.1', '--port', `${PORT}`],
        {
            cwd: process.cwd(),
            stdio: ['ignore', 'pipe', 'pipe'],
        },
    );

    let output = '';
    child.stdout.on('data', (chunk) => {
        output += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
        output += chunk.toString();
    });

    return { child, getOutput: () => output };
};

const waitForServer = async (serverProcess, getOutput) => {
    const timeoutAt = Date.now() + 120_000;

    while (Date.now() < timeoutAt) {
        if (serverProcess.exitCode !== null) {
            throw new Error(
                `Nuxt dev server exited before becoming ready.\n${getOutput()}`,
            );
        }

        try {
            const response = await fetch(`${BASE_URL}${FIXTURE_ROUTE}`);
            if (response.ok) {
                return;
            }
        } catch {
            // Server not ready yet.
        }

        await delay(1_000);
    }

    throw new Error(`Timed out waiting for benchmark fixture route.\n${getOutput()}`);
};

const stopServer = async (serverProcess) => {
    if (serverProcess.exitCode !== null) {
        return;
    }

    serverProcess.kill('SIGINT');
    await new Promise((resolve) => {
        serverProcess.once('exit', resolve);
        setTimeout(resolve, 5_000);
    });
};

const setupApiRoutes = async (page, fixtureCase) => {
    await page.route('**/api/**', async (route) => {
        const url = new URL(route.request().url());
        const toolCallId = url.pathname.match(/^\/api\/chat\/tool-call\/(.+)$/)?.[1];

        if (toolCallId && fixtureCase.toolCallDetails[toolCallId]) {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(fixtureCase.toolCallDetails[toolCallId]),
            });
            return;
        }

        const imageId = url.pathname.match(/^\/api\/files\/view\/(.+)$/)?.[1];
        if (imageId && fixtureCase.generatedImageIds.includes(imageId)) {
            await route.fulfill({
                status: 200,
                contentType: 'image/png',
                body: Buffer.from(ONE_PIXEL_PNG_BASE64, 'base64'),
            });
            return;
        }

        await route.abort('failed');
    });
};

// --- Static (single-render) benchmark ---

const runCaseIteration = async (browser, fixtureCase) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await setupApiRoutes(page, fixtureCase);

    const suffix = fixtureCase.key === 'golden' ? '' : `?case=${encodeURIComponent(fixtureCase.key)}`;
    await page.goto(`${BASE_URL}${FIXTURE_ROUTE}${suffix}`);

    await page.waitForFunction(() => {
        const fixturePage = document.querySelector('[data-testid="markdown-renderer-fixture-page"]');
        const perfStore = window.__markdownRendererPerf;

        return (
            fixturePage?.getAttribute('data-rendered') === 'true' &&
            Boolean(perfStore?.lastRun?.measures?.totalMs)
        );
    });

    const perfRun = await page.evaluate(() => window.__markdownRendererPerf?.lastRun ?? null);
    await context.close();

    if (!perfRun) {
        throw new Error(`No renderer performance run found for case "${fixtureCase.key}"`);
    }

    return perfRun;
};

// --- Streaming benchmark ---

const runStreamingIteration = async (browser, fixtureCase) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await setupApiRoutes(page, fixtureCase);

    const suffix = fixtureCase.key === 'golden'
        ? '?streaming=true'
        : `?case=${encodeURIComponent(fixtureCase.key)}&streaming=true`;

    await page.goto(`${BASE_URL}${FIXTURE_ROUTE}${suffix}`);

    // Wait for all chunks delivered and at least one completed parse
    await page.waitForFunction(() => {
        const el = document.querySelector('[data-testid="markdown-renderer-fixture-page"]');
        if (el?.getAttribute('data-streaming-done') !== 'true') return false;

        const perfStore = window.__markdownRendererPerf;
        const lastCompleted = perfStore?.runs?.filter((r) => r.status === 'completed').pop();
        return Boolean(lastCompleted?.measures?.totalMs);
    }, { timeout: 30_000 });

    const streamingResult = await page.evaluate(() => {
        const perfStore = window.__markdownRendererPerf;
        if (!perfStore) return null;

        const allRuns = perfStore.runs ?? [];
        const completedRuns = allRuns.filter((r) => r.status === 'completed');
        const staleRuns = allRuns.filter((r) => r.status === 'stale');

        return {
            totalRuns: allRuns.length,
            completedRuns: completedRuns.length,
            staleRuns: staleRuns.length,
            completedMeasures: completedRuns.map((r) => r.measures),
        };
    });

    await context.close();

    if (!streamingResult) {
        throw new Error(`No streaming perf data for case "${fixtureCase.key}"`);
    }

    return streamingResult;
};

const main = async () => {
    const requestedIterations = Number.parseInt(
        process.env.MARKDOWN_RENDERER_BENCH_ITERATIONS ?? `${DEFAULT_ITERATIONS}`,
        10,
    );
    const iterations =
        Number.isFinite(requestedIterations) && requestedIterations > 0
            ? requestedIterations
            : DEFAULT_ITERATIONS;

    const runStreaming = process.argv.includes('--streaming');
    const runStatic = !process.argv.includes('--streaming-only');

    const { child: serverProcess, getOutput } = spawnNuxtServer();
    let browser = null;

    try {
        browser = await chromium.launch({
            headless: true,
            chromiumSandbox: false,
        });
        await waitForServer(serverProcess, getOutput);
        console.info(`[markdown-renderer-bench] iterations per case: ${iterations}`);

        // --- Static benchmark ---
        if (runStatic) {
            for (const fixtureCase of CASES) {
                const runs = [];

                for (let index = 0; index < iterations; index += 1) {
                    runs.push(await runCaseIteration(browser, fixtureCase));
                }

                const printableSummary = PHASES.map((phaseName) => {
                    const values = toSortedNumbers(runs.map((run) => run.measures?.[phaseName]));
                    const phaseMedian = median(values);
                    const phaseP95 = percentile(values, 0.95);

                    return `${phaseName}: median=${phaseMedian ?? 'n/a'}ms p95=${
                        phaseP95 === null ? 'n/a' : Number(phaseP95.toFixed(3))
                    }ms`;
                }).join(' | ');

                console.info(`[markdown-renderer-bench] ${fixtureCase.key} -> ${printableSummary}`);
            }
        }

        // --- Streaming benchmark ---
        if (runStreaming || process.argv.includes('--streaming-only')) {
            console.info(`\n[markdown-renderer-bench] === STREAMING ===`);

            const streamingIterations = Math.min(iterations, 6);

            for (const fixtureCase of CASES) {
                const allIterations = [];

                for (let i = 0; i < streamingIterations; i++) {
                    allIterations.push(await runStreamingIteration(browser, fixtureCase));
                }

                // Aggregate across iterations
                const totalRunsCounts = allIterations.map((r) => r.totalRuns);
                const completedRunsCounts = allIterations.map((r) => r.completedRuns);
                const staleRunsCounts = allIterations.map((r) => r.staleRuns);

                // Collect all completed totalMs across all iterations
                const allTotalMs = allIterations.flatMap((r) =>
                    r.completedMeasures
                        .map((m) => m.totalMs)
                        .filter((v) => typeof v === 'number' && Number.isFinite(v)),
                );
                const allProcessorMs = allIterations.flatMap((r) =>
                    r.completedMeasures
                        .map((m) => m.markdownProcessorMs)
                        .filter((v) => typeof v === 'number' && Number.isFinite(v)),
                );

                const sortedTotalMs = toSortedNumbers(allTotalMs);
                const sortedProcessorMs = toSortedNumbers(allProcessorMs);

                const medianCompleted = median(toSortedNumbers(completedRunsCounts));
                const medianStale = median(toSortedNumbers(staleRunsCounts));
                const medianTotal = median(toSortedNumbers(totalRunsCounts));
                const wastedPct = medianTotal > 0
                    ? Number(((medianStale / medianTotal) * 100).toFixed(1))
                    : 0;

                const parts = [
                    `parseCalls: ${medianTotal} (completed=${medianCompleted}, stale=${medianStale}, wasted=${wastedPct}%)`,
                    `totalMs/call: median=${median(sortedTotalMs) ?? 'n/a'}ms p95=${percentile(sortedTotalMs, 0.95)?.toFixed(3) ?? 'n/a'}ms`,
                    `processorMs/call: median=${median(sortedProcessorMs) ?? 'n/a'}ms p95=${percentile(sortedProcessorMs, 0.95)?.toFixed(3) ?? 'n/a'}ms`,
                ];

                console.info(`[markdown-renderer-bench] ${fixtureCase.key} -> ${parts.join(' | ')}`);
            }
        }
    } finally {
        if (browser) {
            await browser.close();
        }
        await stopServer(serverProcess);
    }
};

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
