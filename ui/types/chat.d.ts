import { NodeTypeEnum } from '@/types/enums';

export interface GenerateRequest {
    graph_id: string;
    node_id: string;
    model: string;
    title?: boolean;
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
