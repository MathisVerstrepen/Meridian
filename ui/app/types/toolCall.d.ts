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

export type ToolQuestionAnswerValue = string | string[] | boolean;

export interface ToolQuestionOtherAnswer {
    value?: string | boolean;
    values?: string[];
    other_text: string;
    note?: string;
}

export interface ToolQuestionNoteAnswer {
    value?: string | boolean;
    values?: string[];
    note?: string;
}

export type ToolQuestionAnswer =
    | ToolQuestionAnswerValue
    | ToolQuestionOtherAnswer
    | ToolQuestionNoteAnswer;

export type ToolQuestionAnswerMap = Record<string, ToolQuestionAnswer>;
