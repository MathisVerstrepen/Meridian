import { NodeTypeEnum } from '../../app/types/enums';
import type { BlockSettings, WheelSlot } from '../../app/types/settings';

export const QUICK_WORKFLOW_FIXTURE_ROUTE = '/auth/quick-workflow-wheel-fixture';
export const QUICK_WORKFLOW_FIXTURE_GRAPH_ID = 'quick-workflow-fixture';

const slot = (
    name: string,
    mainBloc: NodeTypeEnum | null,
    options: NodeTypeEnum[] = [],
): WheelSlot => ({ name, mainBloc, options });

export const QUICK_WORKFLOW_FIXTURE_BLOCK_SETTINGS: BlockSettings = {
    contextInputWheel: [
        slot('Slot 1', NodeTypeEnum.TEXT_TO_TEXT, [NodeTypeEnum.PROMPT]),
        slot('Slot 2', NodeTypeEnum.ROUTING, [NodeTypeEnum.PROMPT]),
        slot('Slot 3', NodeTypeEnum.PARALLELIZATION, [NodeTypeEnum.PROMPT]),
        slot('Slot 4', null),
    ],
    contextWheel: [
        slot('Slot 1', NodeTypeEnum.TEXT_TO_TEXT, [NodeTypeEnum.PROMPT]),
        slot('Slot 2', NodeTypeEnum.ROUTING, [NodeTypeEnum.PROMPT]),
        slot('Slot 3', NodeTypeEnum.PARALLELIZATION, [NodeTypeEnum.PROMPT]),
        slot('Slot 4', null),
    ],
    promptInputWheel: [
        slot('Slot 1', NodeTypeEnum.PROMPT),
        slot('Slot 2', null),
        slot('Slot 3', null),
        slot('Slot 4', null),
    ],
    promptOutputWheel: [
        slot('Slot 1', NodeTypeEnum.TEXT_TO_TEXT),
        slot('Slot 2', NodeTypeEnum.ROUTING),
        slot('Slot 3', NodeTypeEnum.PARALLELIZATION),
        slot('Slot 4', null),
    ],
    attachmentInputWheel: [
        slot('Slot 1', NodeTypeEnum.FILE_PROMPT),
        slot('Slot 2', NodeTypeEnum.GITHUB),
        slot('Slot 3', null),
        slot('Slot 4', null),
    ],
    attachmentOutputWheel: [
        slot('Slot 1', NodeTypeEnum.TEXT_TO_TEXT, [NodeTypeEnum.PROMPT]),
        slot('Slot 2', NodeTypeEnum.ROUTING, [NodeTypeEnum.PROMPT]),
        slot('Slot 3', NodeTypeEnum.PARALLELIZATION, [NodeTypeEnum.PROMPT]),
        slot('Slot 4', null),
    ],
};

export const QUICK_WORKFLOW_SETTINGS_KEYS = [
    'contextInputWheel',
    'contextWheel',
    'promptInputWheel',
    'promptOutputWheel',
    'attachmentInputWheel',
    'attachmentOutputWheel',
] as const;
