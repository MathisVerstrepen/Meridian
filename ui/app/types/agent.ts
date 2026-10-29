import type { ToolEnum, ReasoningEffortEnum } from './enums';

export interface AgentModelSettings {
    model: string;
    reasoning_effort: ReasoningEffortEnum | null;
    exclude_reasoning: boolean | null;
    max_tokens: number | null;
    temperature: number | null;
    top_p: number | null;
    top_k: number | null;
    frequency_penalty: number | null;
    presence_penalty: number | null;
    repetition_penalty: number | null;
    structured_output: boolean;
    retry_count: number;
    fallback_model: string | null;
}

export interface AgentProfile {
    handle: string;
    name: string;
    description: string;
    icon: string;
    accentColor: string;
    lifecycle: 'draft' | 'active' | 'archived';
    visibility: 'private' | 'public';
    category: string;
    tags: string[];
    model_settings: AgentModelSettings;
    prompt_stack: { name: string; text: string; enabled: boolean }[];
    tools: ToolEnum[];
}

export interface AgentRecord {
    id: string;
    owner_id: string;
    author: string;
    handle: string;
    profile: AgentProfile;
    version: number;
    verified: boolean;
    source_id: string | null;
    source_version: number | null;
    rating_count: number;
    rating_average: number;
    bookmark_count: number;
    fork_count: number;
    usage_count: number;
    bookmarked: boolean;
    my_rating: number | null;
}

export interface AgentTeam {
    id: string;
    handle: string;
    is_default: boolean;
    name: string;
    description: string;
    members: string[];
}

export interface AgentVersion {
    version: number;
    profile: AgentProfile;
    created_at: string;
}

export interface AgentRun {
    id: string;
    parent_id: string | null;
    agent_id: string | null;
    name: string;
    handle: string;
    version: number | null;
    instructions: string;
    status: string;
    result: string;
    error: string | null;
    pending_tool_call_id?: string | null;
    tool_calls: { id: string; name: string; arguments: JsonValue; result: JsonValue }[];
}
