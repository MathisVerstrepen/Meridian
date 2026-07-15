import { ReasoningEffortEnum } from '../../app/types/enums';

export const REASONING_EFFORT_FIXTURE_ROUTE = '/auth/reasoning-effort-fixture';

export const REASONING_EFFORT_FIXTURE_MASKS = {
    highMediumLow: 28,
    highAndLow: 20,
    none: 0,
} as const;

export const REASONING_EFFORT_FIXTURE_SELECTED = {
    account: ReasoningEffortEnum.MEDIUM,
    unsupported: ReasoningEffortEnum.MAX,
    zero: ReasoningEffortEnum.NONE,
    canvas: ReasoningEffortEnum.MEDIUM,
    unknown: ReasoningEffortEnum.MEDIUM,
} as const;
