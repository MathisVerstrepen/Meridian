import type { Node, Edge } from "@vue-flow/core";

interface Graph {
    id: string; // UUID
    name: string;
    description?: string | null;
    created_at: string; // ISO Date string
    updated_at: string; // ISO Date string
}

interface CompleteGraph {
    graph: Graph;
    nodes: Node[];
    edges: Edge[];
}

interface NodeRequest {
    id: string; // Frontend ID (string)
    graph_id: string; // UUID
    type: string;
    position_x: number;
    position_y: number;
    label?: string | null;
    data?: Record<string, any> | any[] | null; // JSONB
    created_at?: string; // ISO Date string
    updated_at?: string; // ISO Date string
    graph?: Graph;
    outgoing_edges?: EdgeRequest[];
    incoming_edges?: EdgeRequest[];
}

interface EdgeRequest {
    id: string; // Frontend ID (string)
    graph_id: string; // UUID
    source_node_id: string;
    target_node_id: string;
    source_handle_id?: string | null;
    target_handle_id?: string | null;
    type?: string | null;
    label?: string | null;
    animated: boolean;
    style?: Record<string, any> | any[] | null; // JSONB
    data?: Record<string, any> | any[] | null; // JSONB
    created_at?: string; // ISO Date string
    updated_at?: string; // ISO Date string
    graph?: Graph;
    source_node?: NodeRequest;
    target_node?: NodeRequest;
}

interface CompleteGraphRequest {
    graph: Graph;
    nodes: NodeRequest[];
    edges: EdgeRequest[];
}
