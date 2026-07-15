<script setup lang="ts">
import type { CompleteGraph } from '@/types/graph';
import { decodeGraphEditorResponse } from '@/utils/graphResponse';
import {
    GRAPH_RESPONSE_EDGE_COUNT,
    GRAPH_RESPONSE_FIXTURE,
    GRAPH_RESPONSE_IDS,
    GRAPH_RESPONSE_NODE_COUNT,
} from '~~/e2e/fixtures/graphResponseFixture';

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
const loadError = ref('');
const { getGraphById } = useAPI();
const {
    mapEdgeRequestToEdge,
    mapEdgeToEdgeRequest,
    mapNodeRequestToNode,
    mapNodeToNodeRequest,
} = graphMappers();

const errorMessage = (error: unknown): string =>
    error instanceof Error ? error.message : String(error);

const sha256 = async (value: string): Promise<string> => {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join(
        '',
    );
};

const percentile = (durations: number[], ratio: number): number =>
    durations[Math.ceil(durations.length * ratio) - 1] ?? 0;

const timedDecodeAndMap = () => {
    const run = () => {
        const decoded = decodeGraphEditorResponse(GRAPH_RESPONSE_FIXTURE);
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

    return {
        iterations: durations.length,
        payloadBytes: new Blob([JSON.stringify(GRAPH_RESPONSE_FIXTURE)]).size,
        medianMs: percentile(durations, 0.5),
        p95Ms: percentile(durations, 0.95),
    };
};

const rejectionResult = async (
    graphId: string,
    currentGraph: CompleteGraph,
): Promise<{ error: string; countBefore: number; countAfter: number }> => {
    const countBefore = currentGraph.nodes.length;
    let error = '';
    try {
        const decoded = await getGraphById(graphId, false);
        currentGraph.graph = decoded.graph;
        currentGraph.nodes = decoded.nodes;
        currentGraph.edges = decoded.edges;
    } catch (decodeError: unknown) {
        error = errorMessage(decodeError);
    }
    return { error, countBefore, countAfter: currentGraph.nodes.length };
};

onMounted(async () => {
    try {
        const currentGraph = await getGraphById(GRAPH_RESPONSE_IDS.valid, false);
        const firstNode = currentGraph.nodes[0];
        const promptNode = currentGraph.nodes[1];
        const firstEdge = currentGraph.edges[0];
        const defaultEdge = currentGraph.edges[1];
        const reply = typeof firstNode?.data?.reply === 'string' ? firstNode.data.reply : '';
        const decodedForIdentity = decodeGraphEditorResponse(GRAPH_RESPONSE_FIXTURE);
        const sourceData = GRAPH_RESPONSE_FIXTURE.nodes[0]?.data;

        const unsupported = await rejectionResult(GRAPH_RESPONSE_IDS.unsupported, currentGraph);
        const malformed = await rejectionResult(GRAPH_RESPONSE_IDS.malformed, currentGraph);
        const gzipGraph = await getGraphById(GRAPH_RESPONSE_IDS.gzip, false);

        summary.value = {
            graph: currentGraph.graph,
            counts: {
                nodes: currentGraph.nodes.length,
                edges: currentGraph.edges.length,
                expectedNodes: GRAPH_RESPONSE_NODE_COUNT,
                expectedEdges: GRAPH_RESPONSE_EDGE_COUNT,
            },
            node: {
                id: firstNode?.id,
                position: firstNode?.position,
                style: firstNode?.style,
                parentNode: firstNode?.parentNode ?? null,
                promptStyle: promptNode?.style,
                promptParentNode: promptNode?.parentNode,
                promptData: promptNode?.data,
            },
            edge: {
                source: firstEdge?.source,
                target: firstEdge?.target,
                sourceHandle: firstEdge?.sourceHandle,
                targetHandle: firstEdge?.targetHandle,
                label: firstEdge?.label,
                type: firstEdge?.type,
                animated: firstEdge?.animated,
                style: firstEdge?.style,
                data: firstEdge?.data,
                defaultAnimated: defaultEdge?.animated,
            },
            reply: {
                length: reply.length,
                hash: await sha256(reply),
                startsWith: reply.slice(0, 48),
                endsWith: reply.slice(-48),
            },
            opaqueDataPreservedByReference: decodedForIdentity.nodes[0]?.data === sourceData,
            outbound: {
                nodeGraphId: firstNode
                    ? mapNodeToNodeRequest(firstNode, GRAPH_RESPONSE_IDS.valid).graph_id
                    : null,
                edgeGraphId: firstEdge
                    ? mapEdgeToEdgeRequest(firstEdge, GRAPH_RESPONSE_IDS.valid).graph_id
                    : null,
            },
            unsupported,
            malformed,
            gzip: {
                nodes: gzipGraph.nodes.length,
                replyLength:
                    typeof gzipGraph.nodes[0]?.data?.reply === 'string'
                        ? gzipGraph.nodes[0].data.reply.length
                        : 0,
            },
            timing: timedDecodeAndMap(),
        };
    } catch (error: unknown) {
        loadError.value = errorMessage(error);
    }
});
</script>

<template>
    <main
        data-testid="graph-response-fixture-page"
        class="bg-obsidian text-soft-silk min-h-screen overflow-auto p-6"
    >
        <h1 class="text-lg font-semibold">Graph response fixture</h1>
        <p v-if="loadError" data-testid="graph-response-error">{{ loadError }}</p>
        <pre v-else-if="summary" data-testid="graph-response-summary" class="mt-4 text-xs">{{
            JSON.stringify(summary)
        }}</pre>
        <p v-else data-testid="graph-response-loading">Loading fixture…</p>
    </main>
</template>
