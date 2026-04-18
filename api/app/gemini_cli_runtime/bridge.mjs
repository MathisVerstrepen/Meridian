import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

import { CodeAssistServer } from '@google/gemini-cli-core/dist/src/code_assist/server.js';
import { getOauthClient } from '@google/gemini-cli-core/dist/src/code_assist/oauth2.js';
import { setupUser } from '@google/gemini-cli-core/dist/src/code_assist/setup.js';
import { AuthType } from '@google/gemini-cli-core/dist/src/core/contentGenerator.js';
import { LlmRole } from '@google/gemini-cli-core/dist/src/telemetry/types.js';
import {
    DEFAULT_GEMINI_MODEL_AUTO,
    GEMINI_MODEL_ALIAS_AUTO,
    PREVIEW_GEMINI_MODEL_AUTO,
    resolveModel,
} from '@google/gemini-cli-core/dist/src/config/models.js';

const command = process.argv[2] || '';

const readStdin = async () => {
    const chunks = [];
    for await (const chunk of process.stdin) {
        chunks.push(chunk);
    }
    const raw = Buffer.concat(chunks).toString('utf-8').trim();
    return raw ? JSON.parse(raw) : {};
};

const writeJson = (payload) => {
    process.stdout.write(JSON.stringify(payload));
};

const writeJsonLine = (payload) => {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
};

const emitDebugEvent = (payload) => {
    if (command === 'stream') {
        writeJsonLine({
            type: 'debug',
            ...payload,
        });
    }
};

const parseJsonMaybe = (value, fallback) => {
    if (value === null || value === undefined) {
        return fallback;
    }
    if (typeof value !== 'string') {
        return value;
    }
    try {
        return JSON.parse(value);
    } catch {
        return fallback;
    }
};

const normalizeFinishReason = (finishReason, hasToolCalls) => {
    if (hasToolCalls) {
        return 'tool_calls';
    }

    switch (finishReason) {
        case 'STOP':
            return 'stop';
        case 'MAX_TOKENS':
            return 'length';
        case 'SAFETY':
        case 'RECITATION':
            return 'content-filter';
        default:
            return 'other';
    }
};

const normalizeUsage = (usageMetadata) => {
    const promptTokens = Number(usageMetadata?.promptTokenCount || 0);
    const completionTokens = Number(usageMetadata?.candidatesTokenCount || 0);
    return {
        cost: 0,
        is_byok: true,
        total_tokens: promptTokens + completionTokens,
        prompt_tokens: promptTokens,
        completion_tokens: completionTokens,
        prompt_tokens_details: {},
        completion_tokens_details: {},
    };
};

const extractInlineThoughtText = (value) => {
    if (typeof value !== 'string') {
        return null;
    }

    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }

    if (trimmed.startsWith('THOUGHT:')) {
        return {
            thinking: trimmed.slice('THOUGHT:'.length).trim(),
            text: '',
        };
    }

    const bracketThoughtMatch = trimmed.match(/^\[Thought:\s*([\s\S]*?)\]$/i);
    if (bracketThoughtMatch) {
        return {
            thinking: bracketThoughtMatch[1].trim(),
            text: '',
        };
    }

    return null;
};

const splitResponseParts = (parts) => {
    const textParts = [];
    const thinkingParts = [];
    const toolCalls = [];

    for (const part of Array.isArray(parts) ? parts : []) {
        if (part.functionCall) {
            toolCalls.push(buildToolCallPayload(part));
            continue;
        }

        if (!part.text) {
            continue;
        }

        if (part.thought) {
            thinkingParts.push(part.text);
            continue;
        }

        const inlineThought = extractInlineThoughtText(part.text);
        if (inlineThought) {
            if (inlineThought.thinking) {
                thinkingParts.push(inlineThought.thinking);
            }
            if (inlineThought.text) {
                textParts.push(inlineThought.text);
            }
            continue;
        }

        textParts.push(part.text);
    }

    return {
        text: textParts.join(''),
        thinking: thinkingParts.join(''),
        toolCalls,
    };
};

const summarizeMessageParts = (messages) =>
    (Array.isArray(messages) ? messages : []).map((message, index) => {
        const content = Array.isArray(message?.content) ? message.content : [];
        const partTypes = content
            .filter((item) => item && typeof item === 'object')
            .map((item) => {
                if (item.type === 'text') {
                    return 'text';
                }
                if (item.type === 'image_url') {
                    return 'image_url';
                }
                if (item.type === 'file') {
                    const mimeType = String(item.file?.content_type || '').trim();
                    return mimeType ? `file:${mimeType}` : 'file';
                }
                return String(item.type || 'unknown');
            });

        return {
            index,
            role: String(message?.role || 'user'),
            part_types: partTypes,
            tool_call_count: Array.isArray(message?.tool_calls)
                ? message.tool_calls.length
                : 0,
        };
    });

const buildRequestSummary = ({
    payload,
    requestedModel,
    resolvedModel,
    mappedTools,
    systemInstruction,
    generationConfig,
    variantLabel,
}) => ({
    requested_model: requestedModel,
    resolved_model: resolvedModel,
    request_variant: variantLabel,
    message_count: Array.isArray(payload?.messages) ? payload.messages.length : 0,
    message_summary: summarizeMessageParts(payload?.messages),
    has_system_instruction: Boolean(systemInstruction),
    tool_count: Array.isArray(mappedTools?.[0]?.functionDeclarations)
        ? mappedTools[0].functionDeclarations.length
        : 0,
    tool_names: Array.isArray(mappedTools?.[0]?.functionDeclarations)
        ? mappedTools[0].functionDeclarations.map((tool) => tool.name)
        : [],
    generation_config_keys: Object.keys(generationConfig || {}),
    has_response_json_schema: Boolean(generationConfig?.responseJsonSchema),
    thinking_config: generationConfig?.thinkingConfig || null,
});

const formatErrorForTransport = (error, requestSummary) => {
    const normalized = parseJsonMaybe(error instanceof Error ? error.message : error, null);
    if (normalized !== null) {
        return requestSummary
            ? {
                  error: normalized,
                  request_summary: requestSummary,
              }
            : normalized;
    }

    const message = error instanceof Error ? error.message : String(error);
    return requestSummary
        ? {
              message,
              request_summary: requestSummary,
          }
        : message;
};

const extractApiErrorMetadata = (value) => {
    if (!value) {
        return null;
    }

    if (Array.isArray(value)) {
        for (const item of value) {
            const metadata = extractApiErrorMetadata(item);
            if (metadata) {
                return metadata;
            }
        }
        return null;
    }

    if (value instanceof Error) {
        return extractApiErrorMetadata(value.message);
    }

    if (typeof value === 'string') {
        const parsed = parseJsonMaybe(value, null);
        if (parsed !== null) {
            return extractApiErrorMetadata(parsed);
        }

        if (value.includes('NOT_FOUND') || value.includes('"notFound"')) {
            return { code: 404, status: 'NOT_FOUND' };
        }

        return null;
    }

    if (typeof value !== 'object') {
        return null;
    }

    const errorValue = value.error && typeof value.error === 'object' ? value.error : value;
    const code = Number(errorValue.code || 0);
    const status = typeof errorValue.status === 'string' ? errorValue.status : '';
    const reasons = Array.isArray(errorValue.errors)
        ? errorValue.errors
              .map((item) => (item && typeof item.reason === 'string' ? item.reason : ''))
              .filter(Boolean)
        : [];

    if (code || status || reasons.length > 0) {
        return { code, status, reasons };
    }

    return null;
};

const isModelNotFoundError = (error) => {
    const metadata = extractApiErrorMetadata(error);
    if (!metadata) {
        return false;
    }

    return (
        metadata.code === 404 ||
        metadata.status === 'NOT_FOUND' ||
        metadata.reasons?.includes('notFound')
    );
};

const isInvalidArgumentError = (error) => {
    const metadata = extractApiErrorMetadata(error);
    if (!metadata) {
        return false;
    }

    return metadata.code === 400 || metadata.status === 'INVALID_ARGUMENT';
};

const createGeminiCliCoreConfigStub = () => ({
    getBillingSettings: () => ({ overageStrategy: 'BLOCK' }),
    getValidationHandler: () => undefined,
    getExperimentalDynamicModelConfiguration: () => false,
    getCreditsNotificationShown: () => false,
    setCreditsNotificationShown: () => {},
    getProxy: () => undefined,
    isBrowserLaunchSuppressed: () => true,
    isInteractive: () => false,
    getAcpMode: () => false,
});

const resolveRequestedModel = (requestedModel, previewFeaturesEnabled) => {
    const modelToResolve =
        requestedModel === GEMINI_MODEL_ALIAS_AUTO
            ? previewFeaturesEnabled
                ? PREVIEW_GEMINI_MODEL_AUTO
                : DEFAULT_GEMINI_MODEL_AUTO
            : requestedModel;

    return resolveModel(modelToResolve, false, false, false, previewFeaturesEnabled);
};

const executeWithModelFallback = async (requestedModel, operation) => {
    const previewModel = resolveRequestedModel(requestedModel, true);
    emitDebugEvent({
        step: 'select-preview-model',
        requested_model: requestedModel,
        resolved_model: previewModel,
    });

    try {
        return await operation(previewModel);
    } catch (error) {
        const shouldRetryWithStable =
            isModelNotFoundError(error) ||
            (previewModel !== resolveRequestedModel(requestedModel, false) &&
                isInvalidArgumentError(error));

        if (!shouldRetryWithStable) {
            throw error;
        }

        const stableModel = resolveRequestedModel(requestedModel, false);
        if (stableModel === previewModel) {
            throw error;
        }

        emitDebugEvent({
            step: 'fallback-stable-model',
            requested_model: requestedModel,
            resolved_model: stableModel,
        });

        return operation(stableModel);
    }
};

const isGemini3Model = (modelId) => typeof modelId === 'string' && modelId.startsWith('gemini-3');

const isGemini25FlashLiteModel = (modelId) =>
    typeof modelId === 'string' && modelId.includes('gemini-2.5-flash-lite');

const buildThinkingConfig = (settings, resolvedModel) => {
    const gemini3Model = isGemini3Model(resolvedModel);

    if (settings?.is_title_generation || settings?.exclude_reasoning) {
        return gemini3Model
            ? { includeThoughts: false, thinkingLevel: 'MINIMAL' }
            : { includeThoughts: false, thinkingBudget: 0 };
    }

    const rawEffort = settings?.reasoning_effort;
    if (!rawEffort) {
        if (gemini3Model) {
            return { includeThoughts: true };
        }

        return isGemini25FlashLiteModel(resolvedModel)
            ? { includeThoughts: true, thinkingBudget: -1 }
            : { includeThoughts: true };
    }

    const effort = String(rawEffort).toLowerCase();
    const thinkingLevelByEffort = {
        minimal: 'MINIMAL',
        low: 'LOW',
        medium: 'MEDIUM',
        high: 'HIGH',
        max: 'HIGH',
    };
    const thinkingLevel = thinkingLevelByEffort[effort];

    if (!thinkingLevel) {
        return undefined;
    }

    return gemini3Model
        ? {
              includeThoughts: true,
              thinkingLevel,
          }
        : {
              includeThoughts: true,
              thinkingBudget:
                  {
                      minimal: 1024,
                      low: 1024,
                      medium: 8192,
                      high: 24576,
                      max: 24576,
                  }[effort] || 8192,
          };
};

const parseDataUri = (value) => {
    if (typeof value !== 'string') {
        return null;
    }
    const match = value.match(/^data:([^;,]+);base64,(.+)$/);
    if (!match) {
        return null;
    }
    return {
        mimeType: match[1],
        data: match[2],
    };
};

const textPart = (text) => ({ text });

const extractTextContent = (content) => {
    if (typeof content === 'string') {
        return content.trim();
    }
    if (!Array.isArray(content)) {
        return '';
    }

    return content
        .filter((item) => item && typeof item === 'object' && item.type === 'text' && item.text)
        .map((item) => String(item.text))
        .join('\n')
        .trim();
};

const normalizeToolResultPayload = (content) => {
    if (typeof content === 'string') {
        const parsed = parseJsonMaybe(content, null);
        if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) {
            return parsed;
        }
        return { result: content };
    }

    if (Array.isArray(content)) {
        const textContent = content
            .filter((item) => item && typeof item === 'object' && item.type === 'text' && item.text)
            .map((item) => String(item.text))
            .join('\n');
        return { result: textContent };
    }

    if (content && typeof content === 'object') {
        return content;
    }

    return { result: '' };
};

const resolveJsonPointer = (schema, pointer) => {
    if (!pointer.startsWith('#/')) {
        return null;
    }

    let current = schema;
    for (const rawSegment of pointer.slice(2).split('/')) {
        const segment = rawSegment.replace(/~1/g, '/').replace(/~0/g, '~');
        if (!current || typeof current !== 'object' || !(segment in current)) {
            return null;
        }
        current = current[segment];
    }
    return current;
};

const cleanJsonSchema = (schema, rootSchema = schema, resolvingRefs = new Set()) => {
    if (!schema || typeof schema !== 'object') {
        return schema;
    }

    if (Array.isArray(schema)) {
        return schema.map((item) => cleanJsonSchema(item, rootSchema, new Set(resolvingRefs)));
    }

    let resolvedSchema = schema;
    const ref = typeof schema.$ref === 'string' ? schema.$ref : null;
    if (ref && !resolvingRefs.has(ref)) {
        const target = resolveJsonPointer(rootSchema, ref);
        if (target && typeof target === 'object') {
            const nextResolvingRefs = new Set(resolvingRefs);
            nextResolvingRefs.add(ref);
            resolvedSchema = {
                ...target,
                ...Object.fromEntries(Object.entries(schema).filter(([key]) => key !== '$ref')),
            };
            resolvingRefs = nextResolvingRefs;
        }
    }

    const cleaned = { ...resolvedSchema };
    delete cleaned.$schema;
    delete cleaned.$id;
    delete cleaned.$ref;
    delete cleaned.$defs;
    delete cleaned.definitions;
    delete cleaned.title;

    if (cleaned.properties && typeof cleaned.properties === 'object') {
        const nextProps = {};
        for (const [key, value] of Object.entries(cleaned.properties)) {
            nextProps[key] = cleanJsonSchema(value, rootSchema, new Set(resolvingRefs));
        }
        cleaned.properties = nextProps;
        if (!cleaned.type) {
            cleaned.type = 'object';
        }
    }

    if (cleaned.items) {
        cleaned.items = cleanJsonSchema(cleaned.items, rootSchema, new Set(resolvingRefs));
    }

    if (cleaned.additionalProperties && typeof cleaned.additionalProperties === 'object') {
        cleaned.additionalProperties = cleanJsonSchema(
            cleaned.additionalProperties,
            rootSchema,
            new Set(resolvingRefs)
        );
    }

    for (const key of ['allOf', 'anyOf', 'oneOf']) {
        if (Array.isArray(cleaned[key])) {
            cleaned[key] = cleaned[key].map((item) =>
                cleanJsonSchema(item, rootSchema, new Set(resolvingRefs))
            );
        }
    }

    return cleaned;
};

const mapTools = (tools) => {
    if (!Array.isArray(tools) || tools.length === 0) {
        return undefined;
    }

    const functionDeclarations = [];
    for (const tool of tools) {
        const functionDef = tool?.function;
        if (!functionDef || typeof functionDef !== 'object') {
            continue;
        }

        functionDeclarations.push({
            name: String(functionDef.name || ''),
            description: String(functionDef.description || ''),
            parameters: cleanJsonSchema(functionDef.parameters || { type: 'object' }),
        });
    }

    if (functionDeclarations.length === 0) {
        return undefined;
    }

    return [{ functionDeclarations }];
};

const buildToolConfig = (tools) => {
    if (!Array.isArray(tools) || tools.length === 0) {
        return undefined;
    }

    return {
        functionCallingConfig: {
            mode: 'AUTO',
        },
    };
};

const mapUserMessage = (message) => {
    const content = message?.content;
    if (typeof content === 'string') {
        return { role: 'user', parts: [textPart(content)] };
    }

    const parts = [];
    for (const item of Array.isArray(content) ? content : []) {
        if (!item || typeof item !== 'object') {
            continue;
        }

        if (item.type === 'text' && item.text) {
            parts.push(textPart(String(item.text)));
            continue;
        }

        if (item.type === 'image_url' && item.image_url?.url) {
            const dataUri = parseDataUri(String(item.image_url.url));
            if (dataUri) {
                parts.push({
                    inlineData: {
                        mimeType: dataUri.mimeType,
                        data: dataUri.data,
                    },
                });
            }
            continue;
        }

        if (item.type === 'file' && item.file?.file_data) {
            const dataUri = parseDataUri(String(item.file.file_data));
            if (dataUri) {
                parts.push({
                    inlineData: {
                        mimeType: dataUri.mimeType,
                        data: dataUri.data,
                    },
                });
            } else if (item.file.filename) {
                parts.push(
                    textPart(
                        `Attachment reference: ${String(item.file.filename)}`
                    )
                );
            }
        }
    }

    return { role: 'user', parts: parts.length > 0 ? parts : [textPart('')] };
};

const mapAssistantMessage = (message) => {
    const parts = [];
    const content = message?.content;

    if (typeof content === 'string' && content) {
        parts.push(textPart(content));
    } else if (Array.isArray(content)) {
        for (const item of content) {
            if (item && typeof item === 'object' && item.type === 'text' && item.text) {
                parts.push(textPart(String(item.text)));
            }
        }
    }

    if (Array.isArray(message?.tool_calls)) {
        for (const toolCall of message.tool_calls) {
            const functionDef = toolCall?.function;
            if (!functionDef || typeof functionDef !== 'object') {
                continue;
            }

            const providerOptions = toolCall.provider_options || {};
            const geminiOptions = providerOptions['gemini-cli'] || {};
            const args = parseJsonMaybe(functionDef.arguments || '{}', {});
            const mappedPart = {
                functionCall: {
                    name: String(functionDef.name || ''),
                    args: args && typeof args === 'object' ? args : {},
                },
            };

            if (typeof geminiOptions.thoughtSignature === 'string' && geminiOptions.thoughtSignature) {
                mappedPart.thoughtSignature = geminiOptions.thoughtSignature;
            }

            parts.push(mappedPart);
        }
    }

    return { role: 'model', parts };
};

const mapToolMessage = (message) => ({
    role: 'user',
    parts: [
        {
            functionResponse: {
                name: String(message?.name || ''),
                response: normalizeToolResultPayload(message?.content),
            },
        },
    ],
});

const mapMessages = (messages) => {
    const contents = [];
    let systemInstruction;

    for (const message of Array.isArray(messages) ? messages : []) {
        const role = String(message?.role || 'user');

        if (role === 'system') {
            const text = extractTextContent(message?.content);
            if (text) {
                systemInstruction = {
                    role: 'user',
                    parts: [textPart(text)],
                };
            }
            continue;
        }

        if (role === 'assistant') {
            contents.push(mapAssistantMessage(message));
            continue;
        }

        if (role === 'tool') {
            contents.push(mapToolMessage(message));
            continue;
        }

        contents.push(mapUserMessage(message));
    }

    return { contents, systemInstruction };
};

const buildGenerationConfig = (payload, resolvedModel) => {
    const settings = payload?.settings || {};
    const schema = payload?.schema ? cleanJsonSchema(payload.schema) : undefined;
    const mappedTools = mapTools(payload?.tools);
    const generationConfig = {
        temperature:
            settings.temperature === null || settings.temperature === undefined
                ? undefined
                : Number(settings.temperature),
        topP:
            settings.top_p === null || settings.top_p === undefined
                ? undefined
                : Number(settings.top_p),
        topK:
            settings.top_k === null || settings.top_k === undefined
                ? undefined
                : Number(settings.top_k),
        maxOutputTokens:
            settings.max_tokens === null || settings.max_tokens === undefined
                ? undefined
                : Number(settings.max_tokens),
        responseMimeType: schema ? 'application/json' : undefined,
        responseJsonSchema: schema,
        tools: mappedTools,
        toolConfig: buildToolConfig(mappedTools),
        thinkingConfig: buildThinkingConfig(settings, resolvedModel),
    };

    return Object.fromEntries(
        Object.entries(generationConfig).filter(([, value]) => value !== undefined)
    );
};

const buildRequestConfigVariants = (payload, resolvedModel, systemInstruction) => {
    const fullConfig = {
        ...buildGenerationConfig(payload, resolvedModel),
        ...(systemInstruction ? { systemInstruction } : {}),
    };

    const variants = [{ label: 'full', config: fullConfig }];

    if ('temperature' in fullConfig || 'topP' in fullConfig || 'topK' in fullConfig) {
        const { temperature, topP, topK, ...withoutSampling } = fullConfig;
        variants.push({ label: 'no-sampling', config: withoutSampling });
    }

    if ('maxOutputTokens' in fullConfig) {
        const { maxOutputTokens, ...withoutMaxOutputTokens } = fullConfig;
        variants.push({ label: 'no-max-output-tokens', config: withoutMaxOutputTokens });
    }

    if (
        'temperature' in fullConfig ||
        'topP' in fullConfig ||
        'topK' in fullConfig ||
        'maxOutputTokens' in fullConfig
    ) {
        const {
            temperature,
            topP,
            topK,
            maxOutputTokens,
            ...withoutSamplingOrMaxOutput
        } = fullConfig;
        variants.push({
            label: 'no-sampling-or-max-output-tokens',
            config: withoutSamplingOrMaxOutput,
        });
    }

    if (systemInstruction) {
        const { systemInstruction: _ignoredSystemInstruction, ...withoutSystem } = fullConfig;
        variants.push({ label: 'no-system', config: withoutSystem });
    }

    if ('thinkingConfig' in fullConfig) {
        const { thinkingConfig, ...withoutThinking } = fullConfig;
        variants.push({ label: 'no-thinking', config: withoutThinking });
    }

    if (
        'temperature' in fullConfig ||
        'topP' in fullConfig ||
        'topK' in fullConfig ||
        'thinkingConfig' in fullConfig
    ) {
        const { temperature, topP, topK, thinkingConfig, ...withoutSampling } = fullConfig;
        variants.push({ label: 'no-thinking-or-sampling', config: withoutSampling });
    }

    if ('maxOutputTokens' in fullConfig) {
        const {
            temperature,
            topP,
            topK,
            thinkingConfig,
            maxOutputTokens,
            ...minimalConfig
        } = fullConfig;
        variants.push({ label: 'minimal', config: minimalConfig });
    }

    const seen = new Set();
    return variants.filter((variant) => {
        const key = JSON.stringify(variant.config);
        if (seen.has(key)) {
            return false;
        }
        seen.add(key);
        return true;
    });
};

const readUpdatedOAuthCreds = async () => {
    const oauthCredsPath = path.join(os.homedir(), '.gemini', 'oauth_creds.json');
    const raw = await fs.readFile(oauthCredsPath, 'utf-8');
    return JSON.stringify(JSON.parse(raw));
};

const initializeClient = async (_modelId) => {
    const sessionId = randomUUID();
    const config = createGeminiCliCoreConfigStub();
    const client = await getOauthClient(AuthType.LOGIN_WITH_GOOGLE, config);
    const { projectId, userTier, userTierName, paidTier } = await setupUser(client, config);
    const contentGenerator = new CodeAssistServer(
        client,
        projectId,
        {},
        sessionId,
        userTier,
        userTierName,
        paidTier,
        config
    );

    return { contentGenerator };
};

const buildToolCallPayload = (part) => {
    const toolCall = {
        id: randomUUID(),
        type: 'function',
        function: {
            name: String(part.functionCall?.name || ''),
            arguments: JSON.stringify(part.functionCall?.args || {}),
        },
    };

    if (typeof part.thoughtSignature === 'string' && part.thoughtSignature) {
        toolCall.provider_options = {
            'gemini-cli': {
                thoughtSignature: part.thoughtSignature,
            },
        };
    }

    return toolCall;
};

const runValidate = async (payload) => {
    await initializeClient('flash');
    return {
        ok: true,
        oauth_creds_json: await readUpdatedOAuthCreds(),
    };
};

const runGenerate = async (payload) => {
    const requestedModel = String(payload?.model || '');
    const { contentGenerator } = await initializeClient(requestedModel);
    const { contents, systemInstruction } = mapMessages(payload?.messages);
    let lastRequestSummary;
    let response;
    try {
        response = await executeWithModelFallback(requestedModel, (resolvedModel) => {
            const requestVariants = buildRequestConfigVariants(payload, resolvedModel, systemInstruction);

            const tryVariant = async (index) => {
                const variant = requestVariants[index];
                lastRequestSummary = buildRequestSummary({
                    payload,
                    requestedModel,
                    resolvedModel,
                    mappedTools: variant.config.tools,
                    systemInstruction: variant.config.systemInstruction,
                    generationConfig: variant.config,
                    variantLabel: variant.label,
                });
                emitDebugEvent({
                    step: 'generate-variant-attempt',
                    requested_model: requestedModel,
                    resolved_model: resolvedModel,
                    request_variant: variant.label,
                    tool_names: lastRequestSummary.tool_names,
                    generation_config_keys: lastRequestSummary.generation_config_keys,
                });

                try {
                    return await contentGenerator.generateContent(
                        {
                            model: resolvedModel,
                            contents,
                            config: variant.config,
                        },
                        randomUUID(),
                        LlmRole.MAIN
                    );
                } catch (error) {
                    if (!isInvalidArgumentError(error) || index === requestVariants.length - 1) {
                        throw error;
                    }
                    return tryVariant(index + 1);
                }
            };

            return tryVariant(0);
        });
    } catch (error) {
        throw new Error(JSON.stringify(formatErrorForTransport(error, lastRequestSummary)));
    }
    const candidate = response?.candidates?.[0];
    const parsedParts = splitResponseParts(candidate?.content?.parts || []);

    return {
        ok: true,
        text: parsedParts.text,
        thinking: parsedParts.thinking,
        tool_calls: parsedParts.toolCalls,
        finish_reason: normalizeFinishReason(candidate?.finishReason, parsedParts.toolCalls.length > 0),
        usage: normalizeUsage(response?.usageMetadata),
        oauth_creds_json: await readUpdatedOAuthCreds(),
    };
};

const runStream = async (payload) => {
    const requestedModel = String(payload?.model || '');
    const { contentGenerator } = await initializeClient(requestedModel);
    const { contents, systemInstruction } = mapMessages(payload?.messages);
    let lastRequestSummary;
    let streamResponse;
    try {
        streamResponse = await executeWithModelFallback(requestedModel, (resolvedModel) => {
            const requestVariants = buildRequestConfigVariants(payload, resolvedModel, systemInstruction);

            const tryVariant = async (index) => {
                const variant = requestVariants[index];
                lastRequestSummary = buildRequestSummary({
                    payload,
                    requestedModel,
                    resolvedModel,
                    mappedTools: variant.config.tools,
                    systemInstruction: variant.config.systemInstruction,
                    generationConfig: variant.config,
                    variantLabel: variant.label,
                });
                emitDebugEvent({
                    step: 'stream-variant-attempt',
                    requested_model: requestedModel,
                    resolved_model: resolvedModel,
                    request_variant: variant.label,
                    tool_names: lastRequestSummary.tool_names,
                    generation_config_keys: lastRequestSummary.generation_config_keys,
                });

                try {
                    return await contentGenerator.generateContentStream(
                        {
                            model: resolvedModel,
                            contents,
                            config: variant.config,
                        },
                        randomUUID(),
                        LlmRole.MAIN
                    );
                } catch (error) {
                    if (!isInvalidArgumentError(error) || index === requestVariants.length - 1) {
                        throw error;
                    }
                    return tryVariant(index + 1);
                }
            };

            return tryVariant(0);
        });
    } catch (error) {
        throw new Error(JSON.stringify(formatErrorForTransport(error, lastRequestSummary)));
    }
    let usage;
    let toolCallCount = 0;
    let finishReason = 'other';

    for await (const chunk of streamResponse) {
        if (chunk?.usageMetadata) {
            usage = normalizeUsage(chunk.usageMetadata);
        }

        const candidate = chunk?.candidates?.[0];
        const parts = candidate?.content?.parts || [];
        for (const part of parts) {
            if (part.text && part.thought) {
                writeJsonLine({
                    type: 'thinking-delta',
                    delta: part.text,
                });
                continue;
            }

            const inlineThought = extractInlineThoughtText(part.text);
            if (inlineThought?.thinking) {
                writeJsonLine({
                    type: 'thinking-delta',
                    delta: inlineThought.thinking,
                });
                if (inlineThought.text) {
                    writeJsonLine({
                        type: 'text-delta',
                        delta: inlineThought.text,
                    });
                }
                continue;
            }

            if (part.text) {
                writeJsonLine({
                    type: 'text-delta',
                    delta: part.text,
                });
                continue;
            }

            if (part.functionCall) {
                toolCallCount += 1;
                writeJsonLine({
                    type: 'tool-call',
                    tool_call: buildToolCallPayload(part),
                });
            }
        }

        if (candidate?.finishReason) {
            finishReason = normalizeFinishReason(candidate.finishReason, toolCallCount > 0);
        }
    }

    writeJsonLine({
        type: 'finish',
        finish_reason: finishReason,
        usage: usage || normalizeUsage(undefined),
        oauth_creds_json: await readUpdatedOAuthCreds(),
    });
};

const main = async () => {
    const payload = await readStdin();
    if (!command) {
        throw new Error('Missing bridge command.');
    }

    if (command === 'validate') {
        writeJson(await runValidate(payload));
        return;
    }

    if (command === 'generate') {
        writeJson(await runGenerate(payload));
        return;
    }

    if (command === 'stream') {
        await runStream(payload);
        return;
    }

    throw new Error(`Unsupported bridge command: ${command}`);
};

main().catch((error) => {
    const message = error instanceof Error ? parseJsonMaybe(error.message, error.message) : String(error);
    if (command === 'stream') {
        writeJsonLine({
            type: 'error',
            error: message,
        });
    } else {
        writeJson({
            ok: false,
            error: message,
        });
    }
    process.exit(1);
});
