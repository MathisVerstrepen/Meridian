import type { Node, Edge } from '@vue-flow/core';
import type { File } from '@/types/files';
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
    node_count: number;
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

export interface UsageData {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost: number;
    is_byok: boolean;
    prompt_tokens_details: {
        cached_tokens: number;
    };
    completion_tokens_details: {
        reasoning_tokens: number;
    };
}

export interface MessageContentFile {
    filename: string;
    file_data: string; // Base64 encoded file data
}

export interface MessageContentImageURL {
    url: string;
}

export interface MessageContent {
    type: MessageContentTypeEnum;
    text?: string | null;
    file?: MessageContentFile | null;
    image_url?: MessageContentImageURL | null;
}

interface Message {
    role: MessageRoleEnum;
    content: MessageContent[];
    model: string | null;
    node_id: string | null;
    type: NodeTypeEnum;
    data: any | null;
    usageData: UsageData | null;
}

export interface BlockDefinition {
    id: string;
    name: string;
    desc: string;
    icon: string;
    nodeType: string;
    defaultData?: DataPrompt | DataFilePrompt | DataTextToText | DataParallelization;
    minSize?: Record<string, number>;
    color?: string;
}

export interface DataPrompt {
    prompt: string;
}

export interface DataFilePrompt {
    files: File[];
}

export interface DataTextToText {
    model: string;
    reply: string;
    usageData?: UsageData | null;
}

export interface DataParallelization {
    models: Array<{ model: string; reply: string; id: string; usageData?: UsageData | null }>;
    aggregator: { model: string; reply: string };
    defaultModel: string;
    usageData?: UsageData | null;
}

export interface BlockCategories {
    [category: string]: BlockDefinition[];
}
