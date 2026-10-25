export interface StreamRetryStatus {
    attempt: number;
    max_attempts: number;
    delay_seconds: number;
    message: string;
}

export const useStreamRetryStore = defineStore('StreamRetry', () => {
    const statuses = ref<Record<string, Record<string, StreamRetryStatus>>>({});

    const clear = (nodeId: string, modelId?: string) => {
        if (modelId === undefined) {
            delete statuses.value[nodeId];
            return;
        }
        const nodeStatuses = statuses.value[nodeId];
        if (!nodeStatuses) return;
        delete nodeStatuses[modelId];
        if (Object.keys(nodeStatuses).length === 0) delete statuses.value[nodeId];
    };

    const update = (nodeId: string, payload: JsonValue, modelId?: string) => {
        if (payload === null) {
            clear(nodeId, modelId ?? '');
            return;
        }
        if (
            !isJsonObject(payload) ||
            !isRuntimeNumber(payload.attempt) ||
            !isRuntimeNumber(payload.max_attempts) ||
            !isRuntimeNumber(payload.delay_seconds) ||
            !isRuntimeString(payload.message) ||
            !Number.isInteger(payload.attempt) ||
            !Number.isInteger(payload.max_attempts) ||
            payload.attempt < 2 ||
            payload.attempt > payload.max_attempts ||
            !Number.isFinite(payload.delay_seconds) ||
            payload.delay_seconds < 0
        )
            return;

        const nodeStatuses = statuses.value[nodeId] ?? {};
        nodeStatuses[modelId ?? ''] = {
            attempt: payload.attempt,
            max_attempts: payload.max_attempts,
            delay_seconds: payload.delay_seconds,
            message: payload.message,
        };
        statuses.value[nodeId] = nodeStatuses;
    };

    const clearAll = () => {
        statuses.value = {};
    };

    return { statuses, update, clear, clearAll };
});
