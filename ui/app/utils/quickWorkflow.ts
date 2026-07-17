import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { BlockSettings, WheelSlot } from '@/types/settings';

export type QuickWorkflowDirection = 'target' | 'source';
export type QuickWorkflowSettingsKey = keyof Pick<
    BlockSettings,
    | 'contextInputWheel'
    | 'contextWheel'
    | 'promptInputWheel'
    | 'promptOutputWheel'
    | 'attachmentInputWheel'
    | 'attachmentOutputWheel'
>;

export interface QuickWorkflowConfig {
    settingsKey: QuickWorkflowSettingsKey;
    allowedMainBlocks: readonly NodeTypeEnum[];
    allowedOptions: readonly NodeTypeEnum[];
}

const GENERATORS = [
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.ROUTING,
    NodeTypeEnum.PARALLELIZATION,
] as const;
const INPUT_OPTIONS = [NodeTypeEnum.PROMPT, NodeTypeEnum.FILE_PROMPT, NodeTypeEnum.GITHUB] as const;
const ATTACHMENT_OPTIONS = [NodeTypeEnum.FILE_PROMPT, NodeTypeEnum.GITHUB] as const;

const QUICK_WORKFLOW_CONFIG: Record<
    NodeCategoryEnum,
    Record<QuickWorkflowDirection, QuickWorkflowConfig>
> = {
    [NodeCategoryEnum.CONTEXT]: {
        target: {
            settingsKey: 'contextInputWheel',
            allowedMainBlocks: GENERATORS,
            allowedOptions: INPUT_OPTIONS,
        },
        source: {
            settingsKey: 'contextWheel',
            allowedMainBlocks: GENERATORS,
            allowedOptions: INPUT_OPTIONS,
        },
    },
    [NodeCategoryEnum.PROMPT]: {
        target: {
            settingsKey: 'promptInputWheel',
            allowedMainBlocks: [NodeTypeEnum.PROMPT],
            allowedOptions: [],
        },
        source: {
            settingsKey: 'promptOutputWheel',
            allowedMainBlocks: GENERATORS,
            allowedOptions: ATTACHMENT_OPTIONS,
        },
    },
    [NodeCategoryEnum.ATTACHMENT]: {
        target: {
            settingsKey: 'attachmentInputWheel',
            allowedMainBlocks: [NodeTypeEnum.FILE_PROMPT, NodeTypeEnum.GITHUB],
            allowedOptions: [],
        },
        source: {
            settingsKey: 'attachmentOutputWheel',
            allowedMainBlocks: GENERATORS,
            allowedOptions: INPUT_OPTIONS,
        },
    },
};

const BLOCK_IDS: Partial<Record<NodeTypeEnum, string>> = {
    [NodeTypeEnum.PROMPT]: 'primary-prompt-text',
    [NodeTypeEnum.FILE_PROMPT]: 'primary-prompt-file',
    [NodeTypeEnum.GITHUB]: 'primary-github-context',
    [NodeTypeEnum.TEXT_TO_TEXT]: 'primary-model-text-to-text',
    [NodeTypeEnum.PARALLELIZATION]: 'primary-model-parallelization',
    [NodeTypeEnum.ROUTING]: 'primary-model-routing',
};

export const getQuickWorkflowConfig = (
    category: NodeCategoryEnum,
    direction: QuickWorkflowDirection,
): QuickWorkflowConfig => QUICK_WORKFLOW_CONFIG[category][direction];

export const getQuickWorkflowSlots = (
    settings: BlockSettings | null | undefined,
    category: NodeCategoryEnum,
    direction: QuickWorkflowDirection,
): WheelSlot[] | undefined => settings?.[getQuickWorkflowConfig(category, direction).settingsKey];

export const isValidQuickWorkflowSlot = (
    slot: WheelSlot,
    category: NodeCategoryEnum,
    direction: QuickWorkflowDirection,
): boolean => {
    if (!slot.mainBloc) return false;
    const config = getQuickWorkflowConfig(category, direction);
    return (
        config.allowedMainBlocks.includes(slot.mainBloc) &&
        slot.options.every((option) => config.allowedOptions.includes(option))
    );
};

export const getQuickWorkflowBlockId = (nodeType: NodeTypeEnum): string | undefined =>
    BLOCK_IDS[nodeType];

export const getQuickWorkflowHandleId = (category: NodeCategoryEnum, nodeId: string): string =>
    `${category}_${nodeId}`;

export const nodeHasQuickWorkflowHandle = (
    nodeType: string | undefined,
    category: NodeCategoryEnum,
    direction: QuickWorkflowDirection,
): boolean => {
    if (!nodeType) return false;
    if (GENERATORS.includes(nodeType as (typeof GENERATORS)[number])) {
        return direction === 'target' || category === NodeCategoryEnum.CONTEXT;
    }
    if (nodeType === NodeTypeEnum.PROMPT) return category === NodeCategoryEnum.PROMPT;
    if (nodeType === NodeTypeEnum.FILE_PROMPT || nodeType === NodeTypeEnum.GITHUB) {
        return direction === 'source' && category === NodeCategoryEnum.ATTACHMENT;
    }
    return nodeType === NodeTypeEnum.CONTEXT_MERGER && category === NodeCategoryEnum.CONTEXT;
};
