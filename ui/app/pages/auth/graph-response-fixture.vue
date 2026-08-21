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

const summary = shallowRef<object | null>(null);
const loadError = ref('');
const { getGraphById } = useAPI();
const {
    mapEdgeToEdgeRequest,
    mapNodeToNodeRequest,
} = graphMappers();

const errorMessage = <ErrorValue>(error: ErrorValue): string =>
    error instanceof Error ? error.message : String(error);

const sha256 = async (value: string): Promise<string> => {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join(
        '',
    );
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
        const reply = isRuntimeString(firstNode?.data?.reply) ? firstNode.data.reply : '';
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
                    isRuntimeString(gzipGraph.nodes[0]?.data?.reply)
                        ? gzipGraph.nodes[0].data.reply.length
                        : 0,
            },
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
