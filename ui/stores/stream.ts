import type { GenerateRequest } from '@/types/chat';
import type { UsageData } from '@/types/graph';
import type { NodeTypeEnum } from '@/types/enums';
import { SavingStatus } from '@/types/enums';

type StreamChunkCallback = (chunk: string) => Promise<void>;

export interface StreamSession {
    // We have two callbacks here:
    // 1. One for streaming the response in the corresponding block in canvas
    // 2. One for streaming the response in the chat
    chatCallback: StreamChunkCallback | null;
    canvasCallback: StreamChunkCallback | null;
    response: string;
    titleResponse?: string;
    usageData: UsageData | null;
    type: NodeTypeEnum;
    isStreaming: boolean;
    error: Error | null;
    isBackground: boolean;
}

// --- Composables ---
const { sendMessage, connect: connectWebSocket } = useWebSocket();

export const useStreamStore = defineStore('Stream', () => {
    // --- Stores ---
    const { setNeedSave } = useCanvasSaveStore();
    const { error: toastError } = useToast();

    // --- State ---
    const streamSessions = ref<Map<string, StreamSession>>(new Map());

    // --- Private Helper Functions ---

    /**
     * Ensures a session exists for the given node_id, creating one if necessary.
     * @param nodeId - The unique identifier for the stream session.
     * @returns The existing or newly created StreamSession.
     */
    const ensureSession = (
        nodeId: string,
        type: NodeTypeEnum,
        isBackground: boolean = false,
    ): StreamSession => {
        if (!streamSessions.value.has(nodeId)) {
            streamSessions.value.set(nodeId, {
                chatCallback: null,
                canvasCallback: null,
                response: '',
                usageData: null,
                type,
                isStreaming: false,
                error: null,
                isBackground,
            });
        }
        const session = streamSessions.value.get(nodeId);
        if (!session) {
            const msg = `Session for node ID ${nodeId} not found after creation.`;
            toastError(msg, { title: 'Stream Error' });
            throw new Error(`Failed to get or create session for node ID: ${nodeId}`);
        }
        return session;
    };

    // --- Actions ---

    /**
     * Sets the callback function for handling chat-related stream chunks for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param callback - The function to call with each stream chunk.
     */
    const setChatCallback = (
        nodeId: string,
        type: NodeTypeEnum,
        callback: StreamChunkCallback,
    ): void => {
        const session = ensureSession(nodeId, type);
        session.chatCallback = callback;
    };

    /**
     * Removes the chat callback for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     */
    const removeChatCallback = (nodeId: string, type: NodeTypeEnum): void => {
        const session = ensureSession(nodeId, type);
        session.chatCallback = null;
    };

    /**
     * Sets the callback function for handling canvas-related stream chunks for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param callback - The function to call with each stream chunk.
     */
    const setCanvasCallback = (
        nodeId: string,
        type: NodeTypeEnum,
        callback: StreamChunkCallback,
    ): void => {
        const session = ensureSession(nodeId, type);
        session.canvasCallback = callback;
    };

    /**
     * Retrieves the current session for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @returns The current StreamSession for the given node ID.
     */
    const retrieveCurrentSession = (nodeId: string): StreamSession | null => {
        const session = streamSessions.value.get(nodeId);
        if (!session) {
            console.error(`No session found for node ID: ${nodeId}`);
            toastError(`No session found for node ID: ${nodeId}`, {
                title: 'Stream Error',
            });
            return null;
        }
        return session;
    };

    /**
     * Prepares a stream session for a specific node.
     * If the session already exists and is streaming, it returns the existing session.
     * Otherwise, it initializes a new session.
     * @param nodeId - The unique identifier for the stream session.
     * @param type - The type of node (e.g., NodeTypeEnum.PROMPT, NodeTypeEnum.TEXT_TO_TEXT).
     * @returns The prepared StreamSession.
     */
    const preStreamSession = (
        nodeId: string,
        type: NodeTypeEnum,
        isBackground: boolean,
    ): StreamSession => {
        const session = ensureSession(nodeId, type, isBackground);

        if (session.isStreaming) {
            console.warn(`Stream session for node ID ${nodeId} is already active.`);
            return session;
        }

        session.isStreaming = true;
        session.error = null;
        session.response = '';
        session.type = type;
        session.usageData = null;
        session.titleResponse = '';
        session.isBackground = isBackground;

        return session;
    };

    /**
     * Prepares a stream session for a specific node.
     * If the session already exists and is streaming, it returns the existing session.
     * Otherwise, it initializes a new session.
     * @param nodeId - The unique identifier for the stream session.
     * @param type - The type of node (e.g., NodeTypeEnum.PROMPT, NodeTypeEnum.TEXT_TO_TEXT).
     * @param generateRequest - The request object for generating the stream.
     * @param generateTitle - Whether to generate a title for the stream.
     * @param isBackground - Whether the stream is a background process.
     * @returns The prepared StreamSession.
     */
    const startStream = async (
        nodeId: string,
        type: NodeTypeEnum,
        generateRequest: GenerateRequest,
        generateTitle: boolean = false,
        isBackground: boolean = false,
    ): Promise<void> => {
        connectWebSocket(); // Ensure connection is active before sending.
        const session = preStreamSession(nodeId, type, isBackground);

        if (!isBackground && !session.chatCallback && !session.canvasCallback) {
            const msg = `No chat or canvas callback set for node ID: ${nodeId}. Cannot start streaming.`;
            console.error(msg);
            toastError(msg, { title: 'Stream Error' });
            session.error = new Error('Streaming callbacks not set.');
            session.isStreaming = false;
            return;
        }

        try {
            // NOTE: With the current backend implementation, title and content streams
            // cannot be distinguished. This logic sends both requests, but the
            // backend may need future updates to handle them in parallel correctly.
            if (generateTitle) {
                // const titleRequest = { ...generateRequest, title: true };
                // sendMessage({ type: 'start_stream', payload: titleRequest });
            }
            sendMessage({ type: 'start_stream', payload: generateRequest });
        } catch (err) {
            const msg = `Failed to send start_stream message for node ID ${nodeId}`;
            console.error(msg, err);
            toastError(`${msg}: ${(err as Error).message}`, { title: 'Stream Error' });
            session.error =
                err instanceof Error ? err : new Error('An unknown streaming error occurred');
            session.isStreaming = false;
        }
    };

    /**
     * Cancels the stream for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @returns True if the stream was successfully cancelled, false otherwise.
     */
    const cancelStream = async (nodeId: string): Promise<boolean> => {
        const session = streamSessions.value.get(nodeId);
        if (!session || !session.isStreaming) return false;

        const route = useRoute();
        const graphId = route.params.id as string;

        sendMessage({
            type: 'cancel_stream',
            payload: { graph_id: graphId, node_id: nodeId },
        });

        session.isStreaming = false;
        session.error = new Error('Stream cancelled by user.');
        return true;
    };

    // --- WebSocket Event Handlers ---

    /**
     * Handles a stream chunk event for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param payload - The data payload for the stream chunk.
     * @returns void
     */
    const handleStreamChunk = (nodeId: string, payload: string) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        session.response += payload;
        if (session.chatCallback) void session.chatCallback(payload);
        if (session.canvasCallback) void session.canvasCallback(payload);
    };

    /**
     * Handles the end of a stream for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param payload - The data payload for the stream end event.
     * @returns void
     */
    const handleStreamEnd = (nodeId: string, payload: { usage_data?: UsageData }) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        session.isStreaming = false;
        if (payload?.usage_data) {
            session.usageData = payload.usage_data;
        }
        setNeedSave(SavingStatus.NOT_SAVED);
    };

    /**
     * Handles a stream error event for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param payload - The data payload for the stream error event.
     * @returns void
     */
    const handleStreamError = (nodeId: string, payload: { message: string }) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        console.error(`Stream error for node ID ${nodeId}:`, payload.message);
        toastError(`Stream failed: ${payload.message}`, { title: 'Stream Error' });
        session.error = new Error(payload.message);
        session.isStreaming = false;
    };

    // --- Getters / Computed ---

    /**
     * Checks if a specific node is currently streaming.
     * @param nodeId - The unique identifier for the stream session.
     * @returns True if the node is streaming, false otherwise.
     */
    const isNodeStreaming = computed(() => (nodeId: string): boolean => {
        return streamSessions.value.get(nodeId)?.isStreaming ?? false;
    });

    /**
     * Checks if any node is currently streaming.
     * @returns True if any node is streaming, false otherwise.
     */
    const isAnyNodeStreaming = computed((): boolean => {
        for (const session of streamSessions.value.values()) {
            if (session.isStreaming) {
                return true;
            }
        }
        return false;
    });

    return {
        // Actions
        ensureSession,
        setChatCallback,
        removeChatCallback,
        setCanvasCallback,
        preStreamSession,
        startStream,
        cancelStream,
        retrieveCurrentSession,
        // WS Handlers
        handleStreamChunk,
        handleStreamEnd,
        handleStreamError,
        // Getters/State (Read-only)
        isNodeStreaming,
        isAnyNodeStreaming,
    };
});
