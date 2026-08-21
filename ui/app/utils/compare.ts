/**
 * Deep equality check between two values.
 * Handles objects, arrays, primitives, and dates.
 */
export function isDeepEqual<Value>(a: Value, b: Value): boolean {
    if (a === b) return true;

    if (a === null || b === null || !isRuntimeObject(a) || !isRuntimeObject(b)) return false;

    // Handle Date objects
    if (a instanceof Date && b instanceof Date) {
        return a.getTime() === b.getTime();
    }

    // Handle Array
    if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            if (!isDeepEqual(a[i], b[i])) return false;
        }
        return true;
    }

    // Handle plain objects
    const entriesA = Object.entries(a);
    const entriesB = new Map(Object.entries(b));

    if (entriesA.length !== entriesB.size) return false;

    for (const [key, value] of entriesA) {
        if (!entriesB.has(key) || !isDeepEqual(value, entriesB.get(key))) {
            return false;
        }
    }

    return true;
}
import { isRuntimeObject } from '@/utils/runtimeTypes';
