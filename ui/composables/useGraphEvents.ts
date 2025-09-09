import type { NodeTypeEnum, ExecutionPlanDirectionEnum } from '@/types/enums';
import type { ExecutionPlanResponse } from '@/types/chat';
import type { DragZoneHoverEvent } from '@/types/graph';
import type { RepoContent, FileTreeNode } from '@/types/github';

type BusEvents = {
    'update-name': { graphId: string; name: string };
    'node-create': { variant: NodeTypeEnum; fromNodeId: string; options?: NodeTypeEnum[] };
    'node-drag-start': { nodeType: NodeTypeEnum };
    'node-drag-end': Record<string, never>;
    'execution-plan': {
        graphId: string;
        nodeId: string;
        direction: ExecutionPlanDirectionEnum;
        plan: ExecutionPlanResponse;
    };
    'enter-history-sidebar': { over: boolean };
    'open-fullscreen': { open: boolean; rawElement?: string };
    'drag-zone-hover': DragZoneHoverEvent | null;

    'open-github-file-select': { repoContent: RepoContent; nodeId: string };
    'close-github-file-select': { selectedFilePaths: FileTreeNode[]; nodeId: string, branch?: string };

    'open-attachment-select': { nodeId: string | null, selectedFiles: FileSystemObject[] };
    'close-attachment-select': { nodeId: string | null, selectedFiles: FileSystemObject[] };

    'node-group-hover': { nodeId: string } | null;
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
