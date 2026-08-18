/** Runtime type predicates used at schema-free browser and framework boundaries. */
export type RuntimeValue = string | number | boolean | bigint | symbol | object | null | undefined;

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | readonly JsonValue[];
export interface JsonObject {
    [key: string]: JsonValue;
}

export function isRuntimeString<Value>(value: Value): value is Value & string;
export function isRuntimeString<Value>(value: Value): value is Value & string {
    return typeof value === 'string';
}

export function runtimeString<Value>(value: Value, fallback = ''): string {
    return isRuntimeString(value) ? value : fallback;
}

export function isRuntimeNumber<Value>(value: Value): value is Value & number {
    return typeof value === 'number';
}

export function isRuntimeBoolean<Value>(value: Value): value is Value & boolean {
    return typeof value === 'boolean';
}

export function isRuntimeFunction<Value>(value: Value): value is Value & CallableFunction {
    return typeof value === 'function';
}

export function isRuntimeObject<Value>(value: Value): value is Value & (object | null) {
    return typeof value === 'object';
}

export function isJsonValue<Value>(value: Value): value is Value & JsonValue {
    if (
        value === null
        || isRuntimeString(value)
        || isRuntimeNumber(value)
        || isRuntimeBoolean(value)
    ) {
        return true;
    }
    if (Array.isArray(value)) return value.every(isJsonValue);
    if (!isRuntimeObject(value)) return false;
    return Object.values(value).every(isJsonValue);
}

export function isJsonObject<Value>(value: Value): value is Value & JsonObject {
    return isRuntimeObject(value) && value !== null && !Array.isArray(value) && isJsonValue(value);
}

export function jsonObjectOrEmpty<Value>(value: Value): JsonObject {
    return isJsonObject(value) ? value : {};
}

export function isRuntimeUndefined<Value>(value: Value): value is Value & undefined {
    return typeof value === 'undefined';
}

export function runtimeErrorMessage<Value>(value: Value): string | undefined {
    if (value instanceof Error) return value.message;
    if (isRuntimeObject(value) && value !== null && 'message' in value && isRuntimeString(value.message)) {
        return value.message;
    }
    return undefined;
}

export function runtimeErrorStatus<Value>(value: Value): number | undefined {
    if (!isRuntimeObject(value) || value === null) return undefined;
    if ('status' in value && isRuntimeNumber(value.status)) return value.status;
    if ('statusCode' in value && isRuntimeNumber(value.statusCode)) return value.statusCode;
    if (!('response' in value) || !isRuntimeObject(value.response) || value.response === null) {
        return undefined;
    }
    return 'status' in value.response && isRuntimeNumber(value.response.status)
        ? value.response.status
        : undefined;
}

export function runtimeErrorDetail<Value>(value: Value): string | undefined {
    if (!isRuntimeObject(value) || value === null) return undefined;
    if ('data' in value && isRuntimeObject(value.data) && value.data !== null) {
        if ('detail' in value.data && isRuntimeString(value.data.detail)) return value.data.detail;
        if ('message' in value.data && isRuntimeString(value.data.message)) return value.data.message;
    }
    return 'message' in value && isRuntimeString(value.message) ? value.message : undefined;
}

export function firstRouteString(
    value: string | string[] | null | undefined,
): string | undefined {
    return Array.isArray(value) ? value[0] : value ?? undefined;
}

type ElementConstructor<ElementType extends Element> = abstract new (
    ...arguments_: never[]
) => ElementType;

export function elementOrNull<ElementType extends Element>(
    value: EventTarget | null,
    constructor: ElementConstructor<ElementType>,
): ElementType | null {
    return value instanceof constructor ? value : null;
}

export function requireElement<ElementType extends Element>(
    value: EventTarget | null,
    constructor: ElementConstructor<ElementType>,
): ElementType {
    const element = elementOrNull(value, constructor);
    if (!element) throw new TypeError(`Expected ${constructor.name} event target.`);
    return element;
}
