import { describe, expect, it } from 'vitest';
import type { Graph, TopologyPreviewV1 } from '@/types/graph';
import { createEmptyTopologyPreviewV1, toGraphSummary } from '@/utils/graphSummary';

const graphFixture = (topologyPreview?: TopologyPreviewV1): Graph => {
    const graph: Graph = {
        id: 'graph-1',
        name: 'Graph',
        folder_id: null,
        description: null,
        temporary: false,
        pinned: false,
        created_at: '2026-08-31T10:00:00.000Z',
        updated_at: '2026-08-31T12:00:00.000Z',
        custom_instructions: [],
        max_tokens: null,
        temperature: null,
        top_p: null,
        top_k: null,
        frequency_penalty: null,
        presence_penalty: null,
        repetition_penalty: null,
        reasoning_effort: null,
        node_count: 0,
        workspace_id: 'workspace-1',
    };

    if (topologyPreview) graph.topology_preview = topologyPreview;
    return graph;
};

describe('graph summary conversion', () => {
    it('supplies an exact empty V1 preview while preserving raw graph identity', () => {
        const graph = graphFixture();
        const summary = toGraphSummary(graph);

        expect(summary).toBe(graph);
        expect(summary.topology_preview).toEqual({
            version: 1,
            width: 1000,
            height: 600,
            nodes: [],
            edges: [],
        });
        expect(graph.topology_preview).toBe(summary.topology_preview);
    });

    it('preserves a server-provided preview and creates independent empty arrays', () => {
        const preview: TopologyPreviewV1 = {
            version: 1,
            width: 1000,
            height: 600,
            nodes: [{ x: 10, y: 20, width: 100, height: 80 }],
            edges: [],
        };

        expect(toGraphSummary(graphFixture(preview)).topology_preview).toBe(preview);

        const firstEmpty = createEmptyTopologyPreviewV1();
        const secondEmpty = createEmptyTopologyPreviewV1();
        expect(firstEmpty.nodes).not.toBe(secondEmpty.nodes);
        expect(firstEmpty.edges).not.toBe(secondEmpty.edges);
    });
});
