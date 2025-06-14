import type { Message } from '@/types/graph';

interface ChatSession {
    /** The ID of the node the chat session originates from. */
    fromNodeId: string;
    /** The list of messages in the chat session. */
    messages: Message[];
}

export const useChatStore = defineStore('Chat', () => {
    // --- Dependencies ---
    const { getChat } = useAPI();

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
        } catch (error) {
            console.error(`Error fetching chat for node ${nodeId}:`, error);
            fetchError.value =
                error instanceof Error ? error : new Error('Failed to fetch chat messages.');
            session.messages = [];
        } finally {
            isFetching.value = false;
        }
    };

    /**
     * Refreshes the chat messages for a specific node.
     * This is useful for re-fetching messages without closing the chat panel.
     * @param graphId - The ID of the graph containing the node.
     * @param nodeId - The ID of the node to refresh the chat for.
     */
    const refreshChat = async (graphId: string, nodeId: string): Promise<Message[]> => {
        fetchError.value = null;
        const session = getSession(nodeId);
        try {
            const response = await getChat(graphId, nodeId);
            session.messages = response;
        } catch (error) {
            console.error(`Error refreshing chat for node ${nodeId}:`, error);
            fetchError.value =
                error instanceof Error ? error : new Error('Failed to refresh chat messages.');
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
            session.messages[index].content = newText;
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
