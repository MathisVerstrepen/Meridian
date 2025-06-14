export interface Reasoning {
    effort: 'low' | 'medium' | 'high' | null;
    exclude: boolean;
}

export interface GenerateRequest {
    graph_id: string;
    node_id: string;
    model: string;
    reasoning: Reasoning;
    system_prompt: string;
    title?: boolean;
}
