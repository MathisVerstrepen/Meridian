<script setup lang="ts">
import { decodeGraphEditorResponse } from '@/utils/graphResponse';
import {
    GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH,
} from '~~/e2e/fixtures/graphResponseFixture';
import { GRAPH_RESPONSE_PERFORMANCE_FIXTURE } from '~~/e2e/fixtures/graphResponsePerformanceFixture';

definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const summary = shallowRef<Record<string, unknown> | null>(null);
const { mapEdgeRequestToEdge, mapNodeRequestToNode } = graphMappers();

const percentile = (durations: number[], ratio: number): number =>
    durations[Math.ceil(durations.length * ratio) - 1] ?? 0;

onMounted(() => {
    const run = () => {
        const decoded = decodeGraphEditorResponse(GRAPH_RESPONSE_PERFORMANCE_FIXTURE);
        decoded.nodes.map(mapNodeRequestToNode);
        decoded.edges.map(mapEdgeRequestToEdge);
    };

    for (let index = 0; index < 10; index += 1) run();
    const durations: number[] = [];
    for (let index = 0; index < 30; index += 1) {
        const startedAt = performance.now();
        run();
        durations.push(performance.now() - startedAt);
    }
    durations.sort((left, right) => left - right);

    summary.value = {
        nodes: GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT,
        edges: GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT,
        replyLength: GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH,
        timing: {
            iterations: durations.length,
            payloadBytes: new Blob([JSON.stringify(GRAPH_RESPONSE_PERFORMANCE_FIXTURE)]).size,
            medianMs: percentile(durations, 0.5),
            p95Ms: percentile(durations, 0.95),
        },
    };
});
</script>

<template>
    <main
        data-testid="graph-response-performance-fixture-page"
        class="bg-obsidian text-soft-silk min-h-screen overflow-auto p-6"
    >
        <h1 class="text-lg font-semibold">Graph response performance fixture</h1>
        <pre
            v-if="summary"
            data-testid="graph-response-performance-summary"
            class="mt-4 text-xs"
            >{{ JSON.stringify(summary) }}</pre
        >
        <p v-else data-testid="graph-response-performance-loading">Loading fixture…</p>
    </main>
</template>
