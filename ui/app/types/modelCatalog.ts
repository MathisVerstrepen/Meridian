import type { InferenceProvider, ModelDiscoveryWarning } from '@/types/model';

export const MODEL_CATALOG_VERSION = 1 as const;

export const MODEL_CAPABILITY_BITS = {
    textOutput: 1,
    imageOutput: 2,
    videoOutput: 4,
    structuredOutputs: 8,
    nativeTools: 16,
    meridianTools: 32,
    subscription: 64,
} as const;

export const MODEL_SUPPORTED_TOOL_BITS = {
    web_search: 1,
    link_extraction: 2,
    image_generation: 4,
    execute_code: 8,
    visualise: 16,
    ask_user: 32,
} as const;

export interface CompactModelPricing {
    prompt: string;
    completion: string;
    image?: string;
}

export interface CompactModelInfo {
    id: string;
    name: string;
    pricing: CompactModelPricing;
    capabilities: number;
    icon?: string;
    provider?: InferenceProvider;
    created?: string;
    contextLength?: number;
    supportedTools?: number;
    reasoningEfforts?: number;
}

export interface CompactModelCatalogResponse {
    version: typeof MODEL_CATALOG_VERSION;
    data: CompactModelInfo[];
    warnings?: ModelDiscoveryWarning[];
}
