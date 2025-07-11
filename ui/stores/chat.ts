import { MessageContentTypeEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

interface ChatSession {
    /** The ID of the node the chat session originates from. */
    fromNodeId: string;
    /** The list of messages in the chat session. */
    messages: Message[];
}

/**
 * Recursively updates a target object in-place with values from a source object.
 * This function mutates the target object directly to avoid triggering unnecessary
 * Vue reactivity for unchanged properties.
 *
 * @param target - The object to be updated.
 * @param source - The object with the new data.
 */
const updateObjectInPlace = (target: Record<string, any>, source: Record<string, any>): void => {
    // Update or add keys from the source
    for (const key of Object.keys(source)) {
        const targetValue = target[key];
        const sourceValue = source[key];
        const areObjects =
            typeof targetValue === 'object' &&
            targetValue !== null &&
            typeof sourceValue === 'object' &&
            sourceValue !== null;

        if (areObjects) {
            // If both values are arrays, patch the array.
            if (Array.isArray(targetValue) && Array.isArray(sourceValue)) {
                updateArrayInPlace(targetValue, sourceValue);
            }
            // If both values are objects (but not arrays), recurse.
            else if (!Array.isArray(targetValue) && !Array.isArray(sourceValue)) {
                updateObjectInPlace(targetValue, sourceValue);
            }
            // If types mismatch (e.g., object replaced by primitive), just assign.
            else if (targetValue !== sourceValue) {
                target[key] = sourceValue;
            }
        }
        // If they are primitives and different, assign.
        else if (targetValue !== sourceValue) {
            target[key] = sourceValue;
        }
    }

    // Remove keys that exist in the target but not in the source
    for (const key of Object.keys(target)) {
        if (!(key in source)) {
            delete target[key];
        }
    }
};

/**
 * Updates a target array in-place to match a source array, minimizing mutations.
 *
 * @param target - The array to be updated.
 * @param source - The array with the new data.
 */
const updateArrayInPlace = (target: any[], source: any[]): void => {
    // Update existing items
    for (let i = 0; i < Math.min(target.length, source.length); i++) {
        const targetValue = target[i];
        const sourceValue = source[i];
        const areObjects =
            typeof targetValue === 'object' &&
            targetValue !== null &&
            typeof sourceValue === 'object' &&
            sourceValue !== null;

        if (areObjects) {
            // Recurse into objects within the array
            updateObjectInPlace(targetValue, sourceValue);
        } else if (targetValue !== sourceValue) {
            // Update primitive values
            target[i] = sourceValue;
        }
    }

    // Add new items from the source array
    if (source.length > target.length) {
        target.push(...source.slice(target.length));
    }

    // Remove deleted items from the target array
    if (target.length > source.length) {
        target.splice(source.length);
    }
};

export const useChatStore = defineStore('Chat', () => {
    // --- Dependencies ---
    const { getChat } = useAPI();
    const { error } = useToast();

    // --- State ---
    /** Indicates if the chat panel is currently visible. */
    const openChatId = ref<string | null>(null);
    /** Indicates if chat messages are currently being fetched from the API. */
    const isFetching = ref(false);
    /** The model currently selected for the chat. */
    const currentModel = ref<string>('');
    /** Stores any error encountered during the last fetch operation. */
    const fetchError = ref<Error | null>(null);
    /** Indicates if the canvas is ready for interaction. */
    const isCanvasReady = ref(false);
    /** Stores the chat session for each nodeId. */
    const sessions = ref<Map<string, ChatSession>>(new Map());
    /** Store the last opened chat ID. */
    const lastOpenedChatId = ref<string | null>(null);

    // --- Actions ---

    /**
     * Resets the chat state to its initial values.
     * Typically called when closing the chat or before loading a new one.
     */
    const resetChatState = (): void => {
        sessions.value.clear();
        openChatId.value = null;
        isFetching.value = false;
        fetchError.value = null;
    };

    /**
     * Fetches chat messages for a specific node and opens the chat panel.
     * @param graphId - The ID of the graph containing the node.
     * @param nodeId - The ID of the node to load the chat for.
     */
    const loadAndOpenChat = async (graphId: string, nodeId: string): Promise<void> => {
        isFetching.value = true;
        fetchError.value = null;

        const session = getSession(nodeId);
        session.messages = [];
        session.fromNodeId = nodeId;

        try {
            openChatId.value = nodeId;
            lastOpenedChatId.value = nodeId;
            const response = await getChat(graphId, nodeId);
            session.messages = response;
        } catch (err) {
            console.error(`Error fetching chat for node ${nodeId}:`, err);
            fetchError.value =
                err instanceof Error ? err : new Error('Failed to fetch chat messages.');
            error(`Failed to fetch chat messages for node ${nodeId}: ${fetchError.value.message}`, {
                title: 'Chat Error',
            });
            session.messages = [];
        } finally {
            isFetching.value = false;
        }
    };

    /**
     * Refreshes the chat messages for a specific node by deeply patching the
     * existing messages array. This provides the most granular updates possible
     * to prevent UI flickering and preserve component state.
     * @param graphId - The ID of the graph containing the node.
     * @param nodeId - The ID of the node to refresh the chat for.
     */
    const refreshChat = async (graphId: string, nodeId: string): Promise<Message[]> => {
        fetchError.value = null;
        const session = getSession(nodeId);

        try {
            const newMessages = await getChat(graphId, nodeId);
            const oldMessages = session.messages;

            // Use robust helper to patch the main messages array in-place
            // without triggering unnecessary reactivity.
            updateArrayInPlace(oldMessages, newMessages);
        } catch (err) {
            console.error(`Error refreshing chat for node ${nodeId}:`, err);
            fetchError.value =
                err instanceof Error ? err : new Error('Failed to refresh chat messages.');
            error(`Failed to refresh chat messages for node ${nodeId}: ${fetchError.value.message}`, {
                title: 'Chat Error',
            });
            // On error, clear the messages to reflect the failed state.
            session.messages = [];
        }

        return session.messages;
    };

    /**
     * Opens the chat panel without fetching data.
     * Assumes data might already be loaded or will be loaded separately.
     */
    const openChat = (nodeId: string): void => {
        fetchError.value = null;
        openChatId.value = nodeId;
        lastOpenedChatId.value = nodeId;
    };

    /**
     * Closes the chat panel and resets its state.
     */
    const closeChat = (): void => {
        openChatId.value = null;

        // Reset the state fully when closing
        resetChatState();
    };

    /**
     * Removes all messages from a specific index to the end of the list.
     * Useful for regeneration scenarios.
     * @param index - The starting index (inclusive) from which to remove messages.
     */
    const removeAllMessagesFromIndex = (
        index: number,
        nodeId: string = openChatId.value || '',
    ): void => {
        if (!nodeId) {
            console.warn('removeAllMessagesFromIndex: No nodeId provided.');
            return;
        }

        const session = getSession(nodeId);

        if (index < 0 || index > session.messages.length) {
            console.warn(
                `removeAllMessagesFromIndex: Index ${index} is out of bounds for messages array (length ${session.messages.length}).`,
            );
            return;
        }
        if (index < session.messages.length) {
            const removedCount = session.messages.length - index;
            session.messages.splice(index, removedCount);
        }
    };

    /**
     * Removes the last assistant message from the chat session.
     * @param nodeId - The ID of the node to remove the message from.
     */
    const removeLastAssistantMessage = (nodeId: string = openChatId.value || ''): void => {
        if (!nodeId) {
            console.warn('removeLastAssistantMessage: No nodeId provided.');
            return;
        }
        const session = getSession(nodeId);
        const lastMessage = session.messages[session.messages.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
            session.messages.pop();
        } else {
            console.warn('removeLastAssistantMessage: No assistant message to remove.');
        }
    };

    /**
     * Adds a single message to the end of the chat list.
     * @param message - The message object to add.
     */
    const addMessage = (message: Message, nodeId: string = openChatId.value || ''): void => {
        if (!nodeId) {
            console.warn('addMessage: No nodeId provided.');
            return;
        }

        const session = getSession(nodeId);
        session.messages.push(message);
    };

    /**
     * Edits the text of a message at a specific index in the messages array.
     * @param index - The index of the message to edit.
     * @param newText - The new text to set for the message.
     * @param nodeId - The ID of the node to edit the message in.
     */
    const editMessageText = (
        index: number,
        newText: string,
        nodeId: string = openChatId.value || '',
    ): void => {
        if (!nodeId) {
            console.warn('editMessageText: No nodeId provided.');
            return;
        }
        const session = getSession(nodeId);
        if (index < 0 || index >= session.messages.length) {
            console.warn(
                `editMessageText: Index ${index} is out of bounds for messages array (length ${session.messages.length}).`,
            );
            return;
        }
        if (session.messages[index]) {
            // TODO: fix to new content format
            session.messages[index].content.find(
                (content) => content.type === MessageContentTypeEnum.TEXT,
            )!.text = newText;
        } else {
            console.warn(`editMessageText: No message found at index ${index}.`);
        }
    };

    /**
     * Retrieves the most recent message from the messages array.
     *
     * @returns The latest {@link Message} object if available; otherwise, `null` if the array is empty.
     */
    const getLatestMessage = (nodeId: string = openChatId.value || ''): Message | null => {
        if (!nodeId) {
            console.warn('addMessage: No nodeId provided.');
            return null;
        }

        const session = getSession(nodeId);

        if (session.messages.length === 0) {
            return null;
        }
        return session.messages[session.messages.length - 1];
    };

    /**
     * Retrieves the chat session for a specific node ID.
     * If the session does not exist, it creates a new one.
     * @param nodeId - The ID of the node to retrieve the chat session for.
     * @returns The chat session object for the specified node ID.
     */
    const getSession = (nodeId: string): ChatSession => {
        if (!sessions.value.has(nodeId)) {
            sessions.value.set(nodeId, {
                fromNodeId: nodeId,
                messages: [],
            });
        }
        return sessions.value.get(nodeId) as ChatSession;
    };

    /**
     * Migrates a session from an old ID to a new ID.
     * @param oldId - The old session ID to migrate from.
     * @param newId - The new session ID to migrate to.
     */
    const migrateSessionId = (oldId: string, newId: string): void => {
        if (sessions.value.has(oldId)) {
            const session = sessions.value.get(oldId);
            if (session) {
                sessions.value.set(newId, session);
                sessions.value.delete(oldId);
            }
        } else {
            console.warn(`Session with ID ${oldId} does not exist.`);
        }
    };

    return {
        // State
        openChatId,
        isFetching,
        currentModel,
        fetchError,
        isCanvasReady,
        lastOpenedChatId,

        // Actions
        loadAndOpenChat,
        refreshChat,
        openChat,
        closeChat,
        removeAllMessagesFromIndex,
        removeLastAssistantMessage,
        addMessage,
        editMessageText,
        resetChatState,
        getLatestMessage,
        getSession,
        migrateSessionId,
    };
});
