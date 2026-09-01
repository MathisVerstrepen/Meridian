import type { Graph, GraphSummary, TopologyPreviewV1 } from '@/types/graph';

export const createEmptyTopologyPreviewV1 = (): TopologyPreviewV1 => ({
    version: 1,
    width: 1000,
    height: 600,
    nodes: [],
    edges: [],
});

export const toGraphSummary = (graph: Graph): GraphSummary =>
    Object.assign(graph, {
        topology_preview: graph.topology_preview ?? createEmptyTopologyPreviewV1(),
    });
