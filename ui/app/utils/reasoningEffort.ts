import { NodeTypeEnum, REASONING_EFFORTS, ReasoningEffortEnum } from '@/types/enums';
import type { ModelInfo } from '@/types/model';

export const UNKNOWN_REASONING_EFFORTS = -1;
export const ALL_REASONING_EFFORTS = 127;

export const REASONING_EFFORT_LABELS = {
    [ReasoningEffortEnum.MAX]: 'Max',
    [ReasoningEffortEnum.XHIGH]: 'X-High',
    [ReasoningEffortEnum.HIGH]: 'High',
    [ReasoningEffortEnum.MEDIUM]: 'Medium',
    [ReasoningEffortEnum.LOW]: 'Low',
    [ReasoningEffortEnum.MINIMAL]: 'Minimal',
    [ReasoningEffortEnum.NONE]: 'None',
} satisfies Readonly<Record<ReasoningEffortEnum, string>>;

export const isKnownReasoningEffortsMask = (
    value: number | null | undefined,
): value is number => Number.isInteger(value) && value >= 0 && value <= ALL_REASONING_EFFORTS;

export const reasoningEffortBit = (effort: ReasoningEffortEnum): number => {
    const index = REASONING_EFFORTS.indexOf(effort);
    return index === -1 ? 0 : 1 << index;
};

export const isReasoningEffortSupported = (
    effort: ReasoningEffortEnum,
    mask: number | null | undefined,
): boolean => !isKnownReasoningEffortsMask(mask) || (mask & reasoningEffortBit(effort)) !== 0;

type ReasoningCapabilityModel = Pick<ModelInfo, 'id' | 'reasoningEfforts'>;

export const getExactModelReasoningEfforts = (
    modelId: string | null | undefined,
    models: ReadonlyArray<ReasoningCapabilityModel>,
): number | undefined => {
    if (!modelId) return undefined;

    const mask = models.find((model) => model.id === modelId)?.reasoningEfforts;
    return isKnownReasoningEffortsMask(mask) ? mask : undefined;
};

export const getKnownReasoningEffortsUnion = (
    modelIds: ReadonlyArray<string>,
    models: ReadonlyArray<ReasoningCapabilityModel>,
): number | undefined => {
    let union = 0;
    let hasKnownMask = false;

    for (const modelId of new Set(modelIds)) {
        const mask = getExactModelReasoningEfforts(modelId, models);
        if (mask === undefined) continue;
        hasKnownMask = true;
        union |= mask;
    }

    return hasKnownMask ? union : undefined;
};

type CanvasNode = {
    type?: string;
    data?: unknown;
};

const isRecord = <Value>(value: Value): value is Value & Record<string, JsonValue> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const getModelId = <Value>(value: Value): string | null => {
    if (!isRecord(value) || !isRuntimeString(value.model)) return null;
    return value.model;
};

export const getCanvasModelIds = (nodes: ReadonlyArray<CanvasNode>): string[] => {
    const modelIds = new Set<string>();

    for (const node of nodes) {
        if (node.type === NodeTypeEnum.TEXT_TO_TEXT || node.type === NodeTypeEnum.ROUTING) {
            const modelId = getModelId(node.data);
            if (modelId) modelIds.add(modelId);
            continue;
        }

        if (node.type !== NodeTypeEnum.PARALLELIZATION || !isRecord(node.data)) continue;

        const models = node.data.models;
        if (Array.isArray(models)) {
            for (const model of models) {
                const modelId = getModelId(model);
                if (modelId) modelIds.add(modelId);
            }
        }

        const aggregatorModelId = getModelId(node.data.aggregator);
        if (aggregatorModelId) modelIds.add(aggregatorModelId);
    }

    return [...modelIds];
};
import { isRuntimeString } from '@/utils/runtimeTypes';
