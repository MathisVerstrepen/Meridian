interface Architecture {
    input_modalities: string[];
    instruct_type?: string | null;
    modality: string;
    output_modalities: string[];
    tokenizer: string;
}

interface Pricing {
    completion: string;
    image?: string | null;
    internal_reasoning?: string | null;
    prompt: string;
    request?: string | null;
    web_search?: string | null;
}

interface TopProvider {
    context_length?: number | null;
    is_moderated: boolean;
    max_completion_tokens?: number | null;
}

interface ModelInfo {
    architecture: Architecture;
    context_length?: number | null;
    created: number;
    description: string;
    id: string;
    name: string;
    icon: string;
    per_request_limits?: string | null;
    pricing: Pricing;
    supported_parameters: string[];
    top_provider: TopProvider;
}

export interface ResponseModel {
    data: ModelInfo[];
}