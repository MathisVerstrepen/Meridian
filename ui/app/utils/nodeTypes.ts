import { NodeTypeEnum } from '@/types/enums';
import { isRuntimeString, type RuntimeValue } from '@/utils/runtimeTypes';

const NODE_TYPE_VALUES = new Set<string>(Object.values(NodeTypeEnum));

export const isNodeTypeEnum = (value: RuntimeValue): value is NodeTypeEnum =>
    isRuntimeString(value) && NODE_TYPE_VALUES.has(value);

export const nodeTypeOrUndefined = (value: RuntimeValue): NodeTypeEnum | undefined =>
    isNodeTypeEnum(value) ? value : undefined;
