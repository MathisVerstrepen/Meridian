import type { AgentRun } from '@/types/agent';
import {
    isJsonObject,
    isRuntimeString,
    isRuntimeNumber,
    runtimeString,
} from '@/utils/runtimeTypes';

/** Parse both persisted snapshots and live events at their shared UI boundary. */
export function parseAgentRun(value: JsonValue | AgentRun): AgentRun | null {
    if (
        !isJsonObject(value) ||
        !isRuntimeString(value.id) ||
        (value.agent_id !== null && !isRuntimeString(value.agent_id)) ||
        !isRuntimeString(value.name) ||
        !isRuntimeString(value.status)
    )
        return null;
    const tools = Array.isArray(value.tool_calls) ? value.tool_calls : [];
    return {
        id: value.id,
        agent_id: isRuntimeString(value.agent_id) ? value.agent_id : null,
        name: value.name,
        status: value.status,
        parent_id: isRuntimeString(value.parent_id) ? value.parent_id : null,
        handle: runtimeString(value.handle),
        version: isRuntimeNumber(value.version) ? value.version : null,
        instructions: runtimeString(value.instructions),
        result: runtimeString(value.result),
        error: isRuntimeString(value.error) ? value.error : null,
        pending_tool_call_id: isRuntimeString(value.pending_tool_call_id)
            ? value.pending_tool_call_id
            : null,
        tool_calls: tools.flatMap((tool) => {
            if (!isJsonObject(tool) || !isRuntimeString(tool.id) || !isRuntimeString(tool.name))
                return [];
            return [
                {
                    id: tool.id,
                    name: tool.name,
                    arguments: tool.arguments ?? null,
                    result: tool.result ?? null,
                },
            ];
        }),
    };
}
