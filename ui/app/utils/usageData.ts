import type { UsageData, UsageDataRequest } from '@/types/graph';
import {
    isJsonObject,
    isRuntimeBoolean,
    isRuntimeNumber,
    isRuntimeString,
    type JsonValue,
} from '@/utils/runtimeTypes';

const numberDetails = (value: JsonValue): Record<string, number> | null => {
    if (!isJsonObject(value)) return null;
    const details: Record<string, number> = {};
    for (const [key, entry] of Object.entries(value)) {
        if (!isRuntimeNumber(entry)) return null;
        details[key] = entry;
    }
    return details;
};

const nullableString = (value: JsonValue): string | null | undefined => {
    if (value === null) return null;
    return isRuntimeString(value) ? value : undefined;
};

const usageDataRequest = (value: JsonValue): UsageDataRequest | null => {
    if (!isJsonObject(value)) return null;
    const promptDetails = numberDetails(value.prompt_tokens_details);
    const completionDetails = numberDetails(value.completion_tokens_details);
    const costDetails = value.cost_details === undefined ? undefined : numberDetails(value.cost_details);
    const model = nullableString(value.model);
    const finishReason = nullableString(value.finish_reason);
    const nativeFinishReason = nullableString(value.native_finish_reason);
    const requestId = nullableString(value.request_id);
    if (
        !isRuntimeNumber(value.index) ||
        model === undefined ||
        finishReason === undefined ||
        nativeFinishReason === undefined ||
        requestId === undefined ||
        !isRuntimeNumber(value.tool_call_count) ||
        !Array.isArray(value.tool_names) ||
        !value.tool_names.every(isRuntimeString) ||
        !isRuntimeNumber(value.prompt_tokens) ||
        !isRuntimeNumber(value.completion_tokens) ||
        !isRuntimeNumber(value.total_tokens) ||
        !isRuntimeNumber(value.cost) ||
        !isRuntimeBoolean(value.is_byok) ||
        !promptDetails ||
        !completionDetails ||
        costDetails === null
    ) {
        return null;
    }
    return {
        index: value.index,
        model,
        finish_reason: finishReason,
        native_finish_reason: nativeFinishReason,
        request_id: requestId,
        tool_call_count: value.tool_call_count,
        tool_names: value.tool_names,
        prompt_tokens: value.prompt_tokens,
        completion_tokens: value.completion_tokens,
        total_tokens: value.total_tokens,
        cost: value.cost,
        is_byok: value.is_byok,
        prompt_tokens_details: promptDetails,
        completion_tokens_details: completionDetails,
        cost_details: costDetails,
    };
};

export const parseUsageData = (value: JsonValue): UsageData | null => {
    if (!isJsonObject(value)) return null;
    const promptDetails = numberDetails(value.prompt_tokens_details);
    const completionDetails = numberDetails(value.completion_tokens_details);
    const costDetails = value.cost_details === undefined ? undefined : numberDetails(value.cost_details);
    const requests = value.requests === undefined
        ? undefined
        : Array.isArray(value.requests)
          ? value.requests.map(usageDataRequest)
          : null;
    if (
        !isRuntimeNumber(value.prompt_tokens) ||
        !isRuntimeNumber(value.completion_tokens) ||
        !isRuntimeNumber(value.total_tokens) ||
        !isRuntimeNumber(value.cost) ||
        !isRuntimeBoolean(value.is_byok) ||
        !promptDetails ||
        !completionDetails ||
        costDetails === null ||
        requests === null ||
        requests?.some((request) => request === null)
    ) {
        return null;
    }
    return {
        prompt_tokens: value.prompt_tokens,
        completion_tokens: value.completion_tokens,
        total_tokens: value.total_tokens,
        cost: value.cost,
        is_byok: value.is_byok,
        prompt_tokens_details: promptDetails,
        completion_tokens_details: completionDetails,
        cost_details: costDetails,
        requests: requests?.filter((request) => request !== null),
    };
};
