import { v4 as uuidv4 } from 'uuid';

/**
 * Composable function for generating unique node identifiers.
 *
 * @returns An object containing a method to generate unique IDs
 * @property {Function} generateId - Generates a unique string ID using UUID v4
 *
 * @example
 * ```ts
 * const { generateId } = useUniqueId();
 * const nodeId = generateId(); // Returns a UUID v4 string
 * ```
 */
export function useUniqueId() {
    const generateId = (): string => {
        return uuidv4();
    };

    return {
        generateId,
    };
}
