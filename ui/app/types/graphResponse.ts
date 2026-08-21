import type { ReasoningEffortEnum } from '@/types/enums';
import type { Graph } from '@/types/graph';

export const GRAPH_EDITOR_RESPONSE_VERSION = 1 as const;

export type GraphJsonContainer = Record<string, JsonValue> | unknown[];

export interface GraphEditorGraphV1 {
    id: string;
    name: string;
    node_count: number;
    folder_id?: string | null;
    workspace_id?: string | null;
    description?: string | null;
    temporary?: boolean;
    pinned?: boolean;
    created_at?: string | null;
    updated_at?: string | null;
    custom_instructions?: string[];
    max_tokens?: number | null;
    temperature?: number | null;
    top_p?: number | null;
    top_k?: number | null;
    frequency_penalty?: number | null;
    presence_penalty?: number | null;
    repetition_penalty?: number | null;
    reasoning_effort?: ReasoningEffortEnum | null;
}

export interface GraphEditorNodeV1 {
    id: string;
    type: string;
    position_x: number;
    position_y: number;
    width?: string;
    height?: string;
    parent_node_id?: string | null;
    data?: GraphJsonContainer | null;
}

export interface GraphEditorEdgeV1 {
    id: string;
    source_node_id: string;
    target_node_id: string;
    source_handle_id?: string | null;
    target_handle_id?: string | null;
    type?: string | null;
    label?: string | null;
    animated?: boolean;
    style?: GraphJsonContainer | null;
    data?: GraphJsonContainer | null;
}

export interface GraphEditorResponseV1 {
    version: typeof GRAPH_EDITOR_RESPONSE_VERSION;
    graph: GraphEditorGraphV1;
    nodes: GraphEditorNodeV1[];
    edges: GraphEditorEdgeV1[];
}

export interface DecodedGraphEditorNodeV1 extends GraphEditorNodeV1 {
    width: string;
    height: string;
    parent_node_id: string | null;
    data: GraphJsonContainer | null;
}

export interface DecodedGraphEditorEdgeV1 extends GraphEditorEdgeV1 {
    source_handle_id: string | null;
    target_handle_id: string | null;
    type: string | null;
    label: string | null;
    animated: boolean;
    style: GraphJsonContainer | null;
    data: GraphJsonContainer | null;
}

export interface DecodedGraphEditorResponse {
    version: typeof GRAPH_EDITOR_RESPONSE_VERSION;
    graph: Graph;
    nodes: DecodedGraphEditorNodeV1[];
    edges: DecodedGraphEditorEdgeV1[];
}
