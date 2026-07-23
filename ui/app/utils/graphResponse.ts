import { REASONING_EFFORTS } from '@/types/enums';
import type { ReasoningEffortEnum } from '@/types/enums';
import {
    GRAPH_EDITOR_RESPONSE_VERSION,
    type DecodedGraphEditorEdgeV1,
    type DecodedGraphEditorNodeV1,
    type DecodedGraphEditorResponse,
    type GraphJsonContainer,
} from '@/types/graphResponse';

const REASONING_EFFORT_VALUES = new Set<string>(REASONING_EFFORTS);

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const invalid = (path: string, expected: string): never => {
    throw new Error(`Invalid graph response value at ${path}: expected ${expected}`);
};

const requiredString = (value: unknown, path: string): string => {
    if (typeof value !== 'string') return invalid(path, 'a string');
    return value;
};

const requiredNumber = (value: unknown, path: string): number => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return invalid(path, 'a finite number');
    }
    return value;
};

const requiredInteger = (value: unknown, path: string): number => {
    const number = requiredNumber(value, path);
    if (!Number.isSafeInteger(number)) return invalid(path, 'a safe integer');
    return number;
};

const optionalNullableString = (value: unknown, path: string): string | null => {
    if (value === undefined || value === null) return null;
    return requiredString(value, path);
};

const optionalNullableNumber = (value: unknown, path: string): number | null => {
    if (value === undefined || value === null) return null;
    return requiredNumber(value, path);
};

const optionalNullableInteger = (value: unknown, path: string): number | null => {
    if (value === undefined || value === null) return null;
    return requiredInteger(value, path);
};

const optionalBoolean = (value: unknown, path: string, fallback: boolean): boolean => {
    if (value === undefined) return fallback;
    if (typeof value !== 'boolean') return invalid(path, 'a boolean');
    return value;
};

const optionalJsonContainer = (value: unknown, path: string): GraphJsonContainer | null => {
    if (value === undefined || value === null) return null;
    if (Array.isArray(value) || isRecord(value)) return value;
    return invalid(path, 'an object, array, or null');
};

const optionalReasoningEffort = (value: unknown, path: string): ReasoningEffortEnum | null => {
    if (value === undefined || value === null) return null;
    if (typeof value !== 'string' || !REASONING_EFFORT_VALUES.has(value)) {
        return invalid(path, 'a supported reasoning effort or null');
    }
    return value as ReasoningEffortEnum;
};

const customInstructions = (value: unknown, path: string): string[] => {
    if (value === undefined) return [];
    if (!Array.isArray(value)) return invalid(path, 'an array of strings');
    return value.map((instruction, index) =>
        requiredString(instruction, `${path}[${index}]`),
    );
};

const decodeNode = (value: unknown, index: number): DecodedGraphEditorNodeV1 => {
    const path = `nodes[${index}]`;
    if (!isRecord(value)) return invalid(path, 'an object');

    return {
        id: requiredString(value.id, `${path}.id`),
        type: requiredString(value.type, `${path}.type`),
        position_x: requiredNumber(value.position_x, `${path}.position_x`),
        position_y: requiredNumber(value.position_y, `${path}.position_y`),
        width:
            value.width === undefined
                ? '100px'
                : requiredString(value.width, `${path}.width`),
        height:
            value.height === undefined
                ? '100px'
                : requiredString(value.height, `${path}.height`),
        parent_node_id: optionalNullableString(value.parent_node_id, `${path}.parent_node_id`),
        data: optionalJsonContainer(value.data, `${path}.data`),
    };
};

const decodeEdge = (value: unknown, index: number): DecodedGraphEditorEdgeV1 => {
    const path = `edges[${index}]`;
    if (!isRecord(value)) return invalid(path, 'an object');

    return {
        id: requiredString(value.id, `${path}.id`),
        source_node_id: requiredString(value.source_node_id, `${path}.source_node_id`),
        target_node_id: requiredString(value.target_node_id, `${path}.target_node_id`),
        source_handle_id: optionalNullableString(
            value.source_handle_id,
            `${path}.source_handle_id`,
        ),
        target_handle_id: optionalNullableString(
            value.target_handle_id,
            `${path}.target_handle_id`,
        ),
        type: optionalNullableString(value.type, `${path}.type`),
        label: optionalNullableString(value.label, `${path}.label`),
        animated: optionalBoolean(value.animated, `${path}.animated`, false),
        style: optionalJsonContainer(value.style, `${path}.style`),
        data: optionalJsonContainer(value.data, `${path}.data`),
    };
};

export const decodeGraphEditorResponse = (value: unknown): DecodedGraphEditorResponse => {
    if (!isRecord(value)) return invalid('response', 'an object');
    if (value.version !== GRAPH_EDITOR_RESPONSE_VERSION) {
        throw new Error(`Unsupported graph response version: ${String(value.version)}`);
    }
    if (!isRecord(value.graph)) return invalid('graph', 'an object');
    if (!Array.isArray(value.nodes)) return invalid('nodes', 'an array');
    if (!Array.isArray(value.edges)) return invalid('edges', 'an array');

    const graph = value.graph;
    return {
        version: GRAPH_EDITOR_RESPONSE_VERSION,
        graph: {
            id: requiredString(graph.id, 'graph.id'),
            name: requiredString(graph.name, 'graph.name'),
            node_count: requiredInteger(graph.node_count, 'graph.node_count'),
            folder_id: optionalNullableString(graph.folder_id, 'graph.folder_id'),
            workspace_id: optionalNullableString(graph.workspace_id, 'graph.workspace_id'),
            description: optionalNullableString(graph.description, 'graph.description'),
            temporary: optionalBoolean(graph.temporary, 'graph.temporary', false),
            pinned: optionalBoolean(graph.pinned, 'graph.pinned', false),
            created_at: optionalNullableString(graph.created_at, 'graph.created_at'),
            updated_at: optionalNullableString(graph.updated_at, 'graph.updated_at'),
            custom_instructions: customInstructions(
                graph.custom_instructions,
                'graph.custom_instructions',
            ),
            max_tokens: optionalNullableInteger(graph.max_tokens, 'graph.max_tokens'),
            temperature: optionalNullableNumber(graph.temperature, 'graph.temperature'),
            top_p: optionalNullableNumber(graph.top_p, 'graph.top_p'),
            top_k: optionalNullableInteger(graph.top_k, 'graph.top_k'),
            frequency_penalty: optionalNullableNumber(
                graph.frequency_penalty,
                'graph.frequency_penalty',
            ),
            presence_penalty: optionalNullableNumber(
                graph.presence_penalty,
                'graph.presence_penalty',
            ),
            repetition_penalty: optionalNullableNumber(
                graph.repetition_penalty,
                'graph.repetition_penalty',
            ),
            reasoning_effort: optionalReasoningEffort(
                graph.reasoning_effort,
                'graph.reasoning_effort',
            ),
        },
        nodes: value.nodes.map(decodeNode),
        edges: value.edges.map(decodeEdge),
    };
};
