import type { NodeTypeEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

export interface GenerateRequest {
    graph_id: string;
    node_id: string;
    model: string;
    title?: boolean;
    modelId?: string;
    subtype?: 'parallelization-model' | 'parallelization-aggregator';
}

export interface ExecutionPlanStep {
    node_id: string;
    node_type: NodeTypeEnum;
    depends_on: string[];
}

export interface ExecutionPlanResponse {
    steps: ExecutionPlanStep[];
    direction: string;
}

export interface ChatSession {
    /** The ID of the node the chat session originates from. */
    fromNodeId: string;
    /** The list of messages in the chat session. */
    messages: Message[];
}
