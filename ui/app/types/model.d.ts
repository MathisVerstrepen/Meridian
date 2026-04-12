export interface Architecture {
    input_modalities: string[];
    instruct_type?: string | null;
    modality: string;
    output_modalities: string[];
    tokenizer: string;
}

export interface Pricing {
    completion: string;
    image?: string | null;
    internal_reasoning?: string | null;
    prompt: string;
    request?: string | null;
    web_search?: string | null;
}

export type InferenceProvider =
    | 'openrouter'
    | 'claude_agent'
    | 'github_copilot'
    | 'z_ai_coding_plan'
    | 'gemini_cli'
    | 'openai_codex';
export type BillingType = 'metered' | 'subscription';

export interface TopProvider {
    context_length?: number | null;
    is_moderated: boolean;
    max_completion_tokens?: number | null;
}

export interface ModelInfo {
    architecture: Architecture;
    created?: string | null;
    context_length?: number | null;
    id: string;
    name: string;
    icon: string;
    pricing: Pricing;
    provider: InferenceProvider;
    billingType: BillingType;
    requiresConnection: boolean;
    supportsStructuredOutputs: boolean;
    supportsMeridianTools: boolean;
    supportedMeridianToolNames: string[];
    toolsSupport: boolean;
}

export interface ResponseModel {
    data: ModelInfo[];
}

export interface InferenceProviderStatus {
    provider: InferenceProvider;
    label: string;
    isConnected: boolean;
    requiresUserToken: boolean;
}

export interface InferenceProviderStatusResponse {
    providers: InferenceProviderStatus[];
}
