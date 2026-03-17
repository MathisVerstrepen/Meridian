export interface ToolCallDetail {
    id: string;
    node_id: string;
    model_id?: string | null;
    tool_call_id?: string | null;
    tool_name: string;
    status: string;
    arguments: Record<string, unknown> | unknown[];
    result: Record<string, unknown> | unknown[];
    model_context_payload: string;
    created_at?: string | null;
}

export interface ToolActivity {
    toolCallId: string;
    label: string;
    preview: string;
    icon: string;
}
