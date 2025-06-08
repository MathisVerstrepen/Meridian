import type { Node, Edge } from '@vue-flow/core';
import { NodeTypeEnum } from '@/types/enums';

interface Graph {
    id: string; // UUID
    name: string;
    description?: string | null;
    created_at: string; // ISO Date string
    updated_at: string; // ISO Date string
    custom_instructions: string | null;
    max_tokens: number | null;
    temperature: number | null;
    top_p: number | null;
    top_k: number | null;
    frequency_penalty: number | null;
    presence_penalty: number | null;
    repetition_penalty: number | null;
    reasoning_effort: ReasoningEffortEnum | null;
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
    width?: number | null;
    height?: number | null;
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
    markerEnd?: Record<string, any> | any[] | null; // JSONB
}

interface CompleteGraphRequest {
    graph: Graph;
    nodes: NodeRequest[];
    edges: EdgeRequest[];
}

interface Message {
    role: MessageRoleEnum;
    content: string;
    model: string | null;
    node_id: string | null;
    type: NodeTypeEnum;
    data: any | null;
}

export interface BlockDefinition {
    id: string;
    name: string;
    desc: string;
    icon: string;
    nodeType: string;
    defaultData?: DataPrompt | DataTextToText | DataParallelization;
    minSize?: Record<string, number>;
}

export interface DataPrompt {
    prompt: string;
}

export interface DataTextToText {
    model: string;
    reply: string;
}

export interface DataParallelization {
    models: Array<{ model: string; reply: string; id: string }>;
    aggregator: { model: string; reply: string };
    defaultModel: string;
}

export interface BlockCategories {
    [category: string]: BlockDefinition[];
}
