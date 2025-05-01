import type { Message } from '@/types/graph';

export const useChatStore = defineStore('Chat', () => {
    // --- Dependencies ---
    const { getChat } = useAPI();

    // --- State ---
    /** Indicates if the chat panel is currently visible. */
    const isOpen = ref(false);
    /** Indicates if chat messages are currently being fetched from the API. */
    const isFetching = ref(false);
    /** Stores the list of chat messages. */
    const messages = ref<Message[]>([]);
    /** The ID of the node the current chat session originates from. */
    const fromNodeId = ref<string | null>(null);
    /** The model currently selected for the chat. */
    const currentModel = ref<string>('');
    /** Stores any error encountered during the last fetch operation. */
    const fetchError = ref<Error | null>(null);

    // --- Getters (Computed Properties) ---
    /** A simple boolean indicating if there are any messages loaded. */
    const hasMessages = computed(() => messages.value.length > 0);

    // --- Actions ---

    /**
     * Resets the chat state to its initial values.
     * Typically called when closing the chat or before loading a new one.
     */
    const resetChatState = (): void => {
        messages.value = [];
        fromNodeId.value = null;
        isFetching.value = false;
        fetchError.value = null;
    };

    /**
     * Fetches chat messages for a specific node and opens the chat panel.
     * @param graphId - The ID of the graph containing the node.
     * @param nodeId - The ID of the node to load the chat for.
     */
    const loadAndOpenChat = async (
        graphId: string,
        nodeId: string,
    ): Promise<void> => {
        isFetching.value = true;
        fetchError.value = null;
        messages.value = [];
        fromNodeId.value = nodeId;

        try {
            isOpen.value = true;
            const response = await getChat(graphId, nodeId);
            messages.value = response;
        } catch (error) {
            console.error(`Error fetching chat for node ${nodeId}:`, error);
            fetchError.value =
                error instanceof Error
                    ? error
                    : new Error('Failed to fetch chat messages.');
            messages.value = []; // Ensure messages are empty on error
        } finally {
            isFetching.value = false;
        }
    };

    /**
     * Opens the chat panel without fetching data.
     * Assumes data might already be loaded or will be loaded separately.
     */
    const openChat = (): void => {
        fetchError.value = null;
        isOpen.value = true;
    };

    /**
     * Closes the chat panel and resets its state.
     */
    const closeChat = (): void => {
        isOpen.value = false;
        // Reset the state fully when closing
        resetChatState();
    };

    /**
     * Removes all messages from a specific index to the end of the list.
     * Useful for regeneration scenarios.
     * @param index - The starting index (inclusive) from which to remove messages.
     */
    const removeAllMessagesFromIndex = (index: number): void => {
        if (index < 0 || index > messages.value.length) {
            console.warn(
                `removeAllMessagesFromIndex: Index ${index} is out of bounds for messages array (length ${messages.value.length}).`,
            );
            return;
        }
        if (index < messages.value.length) {
            const removedCount = messages.value.length - index;
            messages.value.splice(index, removedCount);
        }
    };

    /**
     * Adds a single message to the end of the chat list.
     * @param message - The message object to add.
     */
    const addMessage = (message: Message): void => {
        messages.value.push(message);
        // Note: Scrolling logic should be handled in the component watching 'messages'
    };

    return {
        // State
        isOpen,
        isFetching,
        messages,
        fromNodeId,
        currentModel,
        fetchError,

        // Getters
        hasMessages,

        // Actions
        loadAndOpenChat,
        openChat,
        closeChat,
        removeAllMessagesFromIndex,
        addMessage,
        resetChatState,
    };
});
