import { ToolEnum } from '@/types/enums';

const TOOL_NAMES = new Set<string>(Object.values(ToolEnum));

export const normalizeToolSelection = (values: readonly string[]): ToolEnum[] =>
    values.filter((value): value is ToolEnum => TOOL_NAMES.has(value));
