import { NodeTypeEnum } from '@/types/enums';
import type { ExecutionPlanResponse } from '@/types/chat';

type BusEvents = {
    'update-name': { graphId: string; name: string };
    'node-create': { variant: string; fromNodeId: string };
    'node-drag-start': { nodeType: NodeTypeEnum };
    'node-drag-end': {};
    'execution-plan': {
        graphId: string;
        nodeId: string;
        direction: 'upstream' | 'downstream' | 'self' | 'all';
        plan: ExecutionPlanResponse;
    };
};

const listeners: { [key in keyof BusEvents]?: Array<(arg: BusEvents[key]) => void> } = {};

/**
 * Registers a callback for a specific event type.
 * @param event - The event type to listen for.
 * @param callback - The function to call when the event is emitted.
 * @returns A function to remove the listener.
 */
function on<K extends keyof BusEvents>(event: K, callback: (arg: BusEvents[K]) => void) {
    if (!listeners[event]) {
        listeners[event] = [];
    }
    listeners[event]!.push(callback);

    return () => {
        const eventListeners = listeners[event];
        if (eventListeners) {
            const index = eventListeners.indexOf(callback);
            if (index > -1) {
                eventListeners.splice(index, 1);
            }
        }
    };
}

/**
 * Emits an event of a specific type with the provided argument.
 * @param event - The event type to emit.
 * @param arg - The argument to pass to the event listeners.
 * @template K - The type of the event key.
 * @template T - The type of the argument for the event.
 * @throws Will throw an error if the event type is not registered.
 */
function emit<K extends keyof BusEvents>(event: K, arg: BusEvents[K]) {
    const eventListeners = listeners[event];
    if (eventListeners) {
        eventListeners.forEach((callback) => callback(arg));
    }
}

export function useGraphEvents() {
    return { on, emit };
}
