/**
 * Deep equality check between two values.
 * Handles objects, arrays, primitives, and dates.
 */
export function isDeepEqual(a: unknown, b: unknown): boolean {
    if (a === b) return true;

    if (a === null || b === null || typeof a !== typeof b) return false;

    if (typeof a !== 'object') return false;

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
    const keysA = Object.keys(a);
    const keysB = b && typeof b === 'object' ? Object.keys(b) : [];

    if (keysA.length !== keysB.length) return false;

    for (const key of keysA) {
        if (!Object.prototype.hasOwnProperty.call(b, key)) return false;
        if (
            typeof a === 'object' &&
            a !== null &&
            typeof b === 'object' &&
            b !== null &&
            !isDeepEqual((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key])
        ) {
            return false;
        }
    }

    return true;
}
