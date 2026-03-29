export interface ToolCallArtifact {
    id: string;
    name: string;
    relative_path: string;
    content_type: string;
    size: number;
    kind: 'image' | 'file';
    tool_call_id?: string;
}

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
    isError?: boolean;
}

export type ToolQuestionInputType = 'single_select' | 'multi_select' | 'boolean' | 'text';

export interface ToolQuestionOption {
    label: string;
    value: string;
    subtext?: string | null;
}

export interface ToolQuestionValidation {
    placeholder?: string | null;
}

export interface ToolQuestionStep {
    id: string;
    question: string;
    input_type: ToolQuestionInputType;
    help_text?: string | null;
    options?: ToolQuestionOption[];
    allow_other?: boolean | null;
    validation?: ToolQuestionValidation | null;
}

export interface ToolQuestionArguments {
    title?: string | null;
    questions: ToolQuestionStep[];
}
