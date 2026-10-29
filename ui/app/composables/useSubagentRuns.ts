import type { MaybeRefOrGetter } from 'vue';
import { parseAgentRun } from '@/utils/agentRuns';

export function useSubagentRuns(
    nodeId: MaybeRefOrGetter<string>,
    execution: MaybeRefOrGetter<JsonObject | undefined>,
) {
    const store = useAgentStore();
    return computed(() => {
        const raw = toValue(execution)?.runs;
        const historical = isJsonObject(raw) ? raw : {};
        return Object.values(store.runs[toValue(nodeId)] ?? historical).flatMap((value) => {
            const run = parseAgentRun(value);
            return run?.parent_id ? [run] : [];
        });
    });
}
