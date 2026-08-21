import type {
    NodePresetPathPart,
    NodePresetUnknownRecord,
    NodePresetValidationIssue,
} from '@/utils/nodePresets/contracts';

const UUID_PATTERN = /^(?:urn:uuid:)?(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\{[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\})$/i;

export function isRecord<Value>(value: Value): value is Value & NodePresetUnknownRecord {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function addIssue(
    issues: NodePresetValidationIssue[],
    path: NodePresetPathPart[],
    code: string,
    message: string,
): void {
    issues.push({ path, code, message });
}

export function requireRecord(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): value is NodePresetUnknownRecord {
    if (isRecord(value)) return true;
    addIssue(issues, path, 'invalid_type', 'Must be an object.');
    return false;
}

export function forbidExtraKeys(
    value: NodePresetUnknownRecord,
    allowed: readonly string[],
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    const allowedSet = new Set(allowed);
    for (const key of Object.keys(value)) {
        if (!allowedSet.has(key)) {
            addIssue(issues, [...path, key], 'extra_field', 'Field is not allowed.');
        }
    }
}

export function validateString(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
    maxLength: number,
    options: { required?: boolean; nullable?: boolean; nonEmpty?: boolean } = {},
): value is string {
    if (value === undefined && !options.required) return false;
    if (value === null && options.nullable) return false;
    if (typeof value !== 'string') {
        addIssue(issues, path, 'invalid_type', 'Must be a string.');
        return false;
    }
    if (options.nonEmpty && value.length === 0) {
        addIssue(issues, path, 'too_short', 'Must not be empty.');
    }
    if ([...value].length > maxLength) {
        addIssue(issues, path, 'too_long', `Must contain at most ${maxLength} characters.`);
    }
    return true;
}

export function validateBoolean(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
    options: { required?: boolean; nullable?: boolean } = {},
): void {
    if (value === undefined && !options.required) return;
    if (value === null && options.nullable) return;
    if (!isRuntimeBoolean(value)) addIssue(issues, path, 'invalid_type', 'Must be a boolean.');
}

export function validateInteger(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
    min: number,
    max: number,
    options: { required?: boolean; nullable?: boolean } = {},
): void {
    if (value === undefined && !options.required) return;
    if (value === null && options.nullable) return;
    if (!isRuntimeNumber(value) || !Number.isInteger(value) || value < min || value > max) {
        addIssue(issues, path, 'invalid_integer', `Must be an integer from ${min} to ${max}.`);
    }
}

export function validateUuid(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!isRuntimeString(value) || !UUID_PATTERN.test(value)) {
        addIssue(issues, path, 'invalid_uuid', 'Must be a UUID string.');
    }
}

export function containsDisallowedControl(value: string): boolean {
    return [...value].some((character) => /\p{C}/u.test(character) && !/\s/u.test(character));
}
import { isRuntimeBoolean, isRuntimeNumber, isRuntimeString } from '@/utils/runtimeTypes';
