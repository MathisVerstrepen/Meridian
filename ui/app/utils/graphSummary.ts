import type { Graph, GraphSummary, TopologyPreviewV2 } from '@/types/graph';

export const createEmptyTopologyPreviewV2 = (): TopologyPreviewV2 => ({
    version: 2,
    width: 1000,
    height: 600,
    nodes: [],
    edges: [],
});

export const toGraphSummary = (graph: Graph): GraphSummary =>
    Object.assign(graph, {
        topology_preview: graph.topology_preview ?? createEmptyTopologyPreviewV2(),
    });
