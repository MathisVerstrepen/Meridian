import { ToolEnum } from '@/types/enums';
import type {
    CompactModelCatalogResponse,
    CompactModelInfo,
    CompactModelPricing,
} from '@/types/modelCatalog';
import {
    MODEL_CAPABILITY_BITS,
    MODEL_CATALOG_VERSION,
    MODEL_SUPPORTED_TOOL_BITS,
} from '@/types/modelCatalog';
import type {
    InferenceProvider,
    ModelDiscoveryWarning,
    ModelInfo,
    ResponseModel,
} from '@/types/model';

const INFERENCE_PROVIDERS: InferenceProvider[] = [
    'openrouter',
    'claude_agent',
    'github_copilot',
    'z_ai_coding_plan',
    'alibaba_token_plan',
    'gemini_cli',
    'openai_codex',
    'opencode_go',
];

const isInferenceProvider = <Value>(value: Value): value is Value & InferenceProvider =>
    isRuntimeString(value) && INFERENCE_PROVIDERS.some((provider) => provider === value);

const TOOL_BITS = [
    [ToolEnum.WEB_SEARCH, MODEL_SUPPORTED_TOOL_BITS.web_search],
    [ToolEnum.LINK_EXTRACTION, MODEL_SUPPORTED_TOOL_BITS.link_extraction],
    [ToolEnum.IMAGE_GENERATION, MODEL_SUPPORTED_TOOL_BITS.image_generation],
    [ToolEnum.EXECUTE_CODE, MODEL_SUPPORTED_TOOL_BITS.execute_code],
    [ToolEnum.VISUALISE, MODEL_SUPPORTED_TOOL_BITS.visualise],
    [ToolEnum.ASK_USER, MODEL_SUPPORTED_TOOL_BITS.ask_user],
] as const;

const isRecord = <Value>(value: Value): value is Value & Record<string, JsonValue> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const invalid = (path: string, expected: string): never => {
    throw new Error(`Invalid model catalog value at ${path}: expected ${expected}`);
};

const requiredString = (value: RuntimeValue, path: string): string => {
    if (!isRuntimeString(value)) return invalid(path, 'a string');
    return value;
};

const optionalString = (value: RuntimeValue, path: string): string | undefined => {
    if (value === undefined) return undefined;
    return requiredString(value, path);
};

const optionalNullableString = (
    value: RuntimeValue,
    path: string,
): string | null | undefined => {
    if (value === undefined) return undefined;
    if (value === null) return null;
    if (isRuntimeString(value)) return value;
    return invalid(path, 'a string or null');
};

const requiredMask = (value: RuntimeValue, path: string): number => {
    if (
        !isRuntimeNumber(value) ||
        !Number.isSafeInteger(value) ||
        value < 0 ||
        value > 0x7fffffff
    ) {
        return invalid(path, 'a non-negative 32-bit integer');
    }
    return value;
};

const optionalInteger = (value: RuntimeValue, path: string): number | undefined => {
    if (value === undefined) return undefined;
    if (!isRuntimeNumber(value) || !Number.isSafeInteger(value)) {
        return invalid(path, 'a safe integer');
    }
    return value;
};

const parseProvider = (value: RuntimeValue, path: string): InferenceProvider => {
    if (!isInferenceProvider(value)) {
        return invalid(path, 'a supported inference provider');
    }
    return value;
};

const parsePricing = (value: RuntimeValue, path: string): CompactModelPricing => {
    if (!isRecord(value)) return invalid(path, 'an object');
    const image = optionalString(value.image, `${path}.image`);
    const pricing = {
        prompt: requiredString(value.prompt, `${path}.prompt`),
        completion: requiredString(value.completion, `${path}.completion`),
    };
    if (image !== undefined) Object.assign(pricing, { image });
    return pricing;
};

const parseCompactModel = (value: RuntimeValue, index: number): CompactModelInfo => {
    const path = `data[${index}]`;
    if (!isRecord(value)) return invalid(path, 'an object');

    const icon = optionalString(value.icon, `${path}.icon`);
    const created = optionalString(value.created, `${path}.created`);
    const contextLength = optionalInteger(value.contextLength, `${path}.contextLength`);
    const provider =
        value.provider === undefined
            ? undefined
            : parseProvider(value.provider, `${path}.provider`);
    const supportedTools =
        value.supportedTools === undefined
            ? undefined
            : requiredMask(value.supportedTools, `${path}.supportedTools`);
    const reasoningEfforts = optionalInteger(value.reasoningEfforts, `${path}.reasoningEfforts`);

    const model = {
        id: requiredString(value.id, `${path}.id`),
        name: requiredString(value.name, `${path}.name`),
        pricing: parsePricing(value.pricing, `${path}.pricing`),
        capabilities: requiredMask(value.capabilities, `${path}.capabilities`),
    };
    if (icon !== undefined) Object.assign(model, { icon });
    if (provider !== undefined) Object.assign(model, { provider });
    if (created !== undefined) Object.assign(model, { created });
    if (contextLength !== undefined) Object.assign(model, { contextLength });
    if (supportedTools !== undefined) Object.assign(model, { supportedTools });
    if (reasoningEfforts !== undefined) Object.assign(model, { reasoningEfforts });
    return model;
};

const parseWarning = (value: RuntimeValue, index: number): ModelDiscoveryWarning => {
    const path = `warnings[${index}]`;
    if (!isRecord(value)) return invalid(path, 'an object');

    const actionLabel = optionalNullableString(value.actionLabel, `${path}.actionLabel`);
    const actionUrl = optionalNullableString(value.actionUrl, `${path}.actionUrl`);

    const warning = {
        provider: parseProvider(value.provider, `${path}.provider`),
        title: requiredString(value.title, `${path}.title`),
        message: requiredString(value.message, `${path}.message`),
    };
    if (actionLabel !== undefined) Object.assign(warning, { actionLabel });
    if (actionUrl !== undefined) Object.assign(warning, { actionUrl });
    return warning;
};

const parseCatalog = <Value>(value: Value): CompactModelCatalogResponse => {
    if (!isRecord(value)) return invalid('response', 'an object');
    if (value.version !== MODEL_CATALOG_VERSION) {
        throw new Error(`Unsupported model catalog version: ${String(value.version)}`);
    }
    if (!Array.isArray(value.data)) return invalid('data', 'an array');
    const warnings =
        value.warnings === undefined
            ? undefined
            : Array.isArray(value.warnings)
              ? value.warnings.map(parseWarning)
              : invalid('warnings', 'an array');

    const catalog = {
        version: MODEL_CATALOG_VERSION,
        data: value.data.map(parseCompactModel),
    };
    if (warnings !== undefined) Object.assign(catalog, { warnings });
    return catalog;
};

const hasBit = (mask: number, bit: number): boolean => (mask & bit) !== 0;

const decodeModel = (model: CompactModelInfo): ModelInfo => {
    const capabilities = model.capabilities;
    const supportedTools = model.supportedTools ?? 0;
    const isSubscription = hasBit(capabilities, MODEL_CAPABILITY_BITS.subscription);
    const outputModalities: string[] = [];

    if (hasBit(capabilities, MODEL_CAPABILITY_BITS.textOutput)) outputModalities.push('text');
    if (hasBit(capabilities, MODEL_CAPABILITY_BITS.imageOutput)) outputModalities.push('image');
    if (hasBit(capabilities, MODEL_CAPABILITY_BITS.videoOutput)) outputModalities.push('video');

    const pricing = {
        prompt: model.pricing.prompt,
        completion: model.pricing.completion,
    };
    if (model.pricing.image !== undefined) {
        Object.assign(pricing, { image: model.pricing.image });
    }

    const decoded = {
        architecture: {
            // These normalized fields are required by ModelInfo but are intentionally absent
            // from the compact wire contract and have no model-catalog UI consumers.
            input_modalities: [],
            modality: '',
            output_modalities: outputModalities,
            tokenizer: '',
        },
        id: model.id,
        name: model.name,
        icon: model.icon ?? '',
        pricing,
        provider: model.provider ?? 'openrouter',
        billingType: isSubscription ? ('subscription' as const) : ('metered' as const),
        requiresConnection: isSubscription,
        supportsStructuredOutputs: hasBit(
            capabilities,
            MODEL_CAPABILITY_BITS.structuredOutputs,
        ),
        supportsMeridianTools: hasBit(capabilities, MODEL_CAPABILITY_BITS.meridianTools),
        supportedMeridianToolNames: TOOL_BITS.filter(([, bit]) => hasBit(supportedTools, bit)).map(
            ([tool]) => tool,
        ),
        toolsSupport: hasBit(capabilities, MODEL_CAPABILITY_BITS.nativeTools),
        reasoningEfforts: model.reasoningEfforts ?? 0,
    };
    if (model.created !== undefined) Object.assign(decoded, { created: model.created });
    if (model.contextLength !== undefined) {
        Object.assign(decoded, { context_length: model.contextLength });
    }
    return decoded;
};

export const decodeModelCatalog = <Value>(value: Value): ResponseModel => {
    const catalog = parseCatalog(value);
    return {
        data: catalog.data.map(decodeModel),
        warnings: catalog.warnings ?? [],
    };
};
import { isRuntimeNumber, isRuntimeString } from '@/utils/runtimeTypes';
