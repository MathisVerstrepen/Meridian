import type { GenerateRequest } from '@/types/chat';
import type { UsageData } from '@/types/graph';
import { SavingStatus, NodeTypeEnum } from '@/types/enums';

type StreamChunkCallback = (chunk: string, modelId: string | undefined) => void;
type StreamFinishedCallback = (session: StreamSession) => void;

export interface StreamSession {
    // We have two callbacks here:
    // 1. One for streaming the response in the corresponding block in canvas
    // 2. One for streaming the response in the chat
    chatCallback: StreamChunkCallback | null;
    canvasCallback: StreamChunkCallback | null;
    onFinished: StreamFinishedCallback | null;
    response: string;
    titleResponse?: string;
    usageData: UsageData | null;
    type: NodeTypeEnum;
    isStreaming: boolean;
    error: Error | null;
    isBackground: boolean;
    routingPromiseResolve?: (value: StreamSession) => void;
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
                onFinished: null,
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
     * Sets the callback function to be called when the stream finishes for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param callback - The function to call when the stream finishes.
     */
    const setOnFinishedCallback = (
        nodeId: string,
        type: NodeTypeEnum,
        callback: StreamFinishedCallback,
    ): void => {
        const session = ensureSession(nodeId, type);
        session.onFinished = callback;
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
     * Initiates a generation stream via WebSocket.
     * @param nodeId - The unique identifier for the stream session.
     * @param type - The type of node, which determines the backend logic to run.
     * @param generateRequest - The request object for generating the stream.
     * @param generateTitle - Whether to generate a title for the stream.
     * @param isBackground - Whether the stream is a background process.
     * @returns A promise that resolves with the stream session object. For routing, it resolves when the result is received.
     */
    const startStream = (
        nodeId: string,
        type: NodeTypeEnum,
        generateRequest: GenerateRequest,
        generateTitle: boolean = false,
        isBackground: boolean = false,
    ): Promise<StreamSession> => {
        connectWebSocket(); // Ensure connection is active before sending.
        const session = preStreamSession(nodeId, type, isBackground);

        if (!isBackground && !session.chatCallback && !session.canvasCallback) {
            const msg = `No chat or canvas callback set for node ID: ${nodeId}. Cannot start streaming.`;
            console.error(msg);
            toastError(msg, { title: 'Stream Error' });
            session.error = new Error('Streaming callbacks not set.');
            session.isStreaming = false;
            return Promise.reject(session.error);
        }

        try {
            const payloadWithStreamType = { ...generateRequest, stream_type: type, title: false };
            sendMessage({ type: 'start_stream', payload: payloadWithStreamType });

            if (generateTitle) {
                const payloadForTitle = { ...payloadWithStreamType, title: true };
                sendMessage({ type: 'start_stream', payload: payloadForTitle });
            }

            if (type === NodeTypeEnum.ROUTING) {
                return new Promise((resolve) => {
                    session.routingPromiseResolve = resolve;
                });
            }
            return Promise.resolve(session);
        } catch (err) {
            const msg = `Failed to send start_stream message for node ID ${nodeId}`;
            console.error(msg, err);
            const error =
                err instanceof Error ? err : new Error('An unknown streaming error occurred');
            toastError(`${msg}: ${error.message}`, { title: 'Stream Error' });
            session.error = error;
            session.isStreaming = false;
            return Promise.reject(error);
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
    const handleStreamChunk = (
        nodeId: string,
        payload: string,
        modelId: string | undefined = undefined,
    ) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        session.response += payload;
        if (session.chatCallback) void session.chatCallback(payload, modelId);
        if (session.canvasCallback) void session.canvasCallback(payload, modelId);
    };

    /**
     * Handles the end of a stream for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param payload - The data payload for the stream end event.
     * @returns void
     */
    const handleStreamEnd = (
        nodeId: string,
        payload: { usage_data?: UsageData },
        modelId: string | undefined = undefined,
    ) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        if (!modelId) {
            session.isStreaming = false;
            if (payload?.usage_data) {
                session.usageData = payload.usage_data;
            }
            setNeedSave(SavingStatus.NOT_SAVED);

            // Call onFinished callback if set
            if (session.onFinished) {
                session.onFinished(session);
                session.onFinished = null;
            }

            if (session.routingPromiseResolve) {
                session.routingPromiseResolve(session);
                session.routingPromiseResolve = undefined;
            }
        } else {
            if (session.onFinished) {
                session.onFinished(session);
            }
        }
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

        // Call onFinished callback if set
        if (session.onFinished) {
            session.onFinished(session);
            session.onFinished = null; // Clear callback to prevent memory leaks
        }
    };

    /**
     * Handles a routing response event for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param payload - The data payload for the routing response event.
     * @returns void
     */
    const handleRoutingResponse = (nodeId: string, payload: unknown) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        session.response = JSON.stringify(payload);
    };

    /**
     * Handles the title response event for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param payload - The data payload for the title response event.
     * @returns void
     */
    const handleTitleResponse = (nodeId: string, payload: { title: string }) => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return;

        console.log(`Received title for node ID ${nodeId}:`, payload.title);

        // Remove [START] and [END] markers if present
        session.titleResponse = payload.title
            .replace(/\[START\]/, '')
            .replace(/\[END\]/, '')
            .trim();
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
        setOnFinishedCallback,
        preStreamSession,
        startStream,
        cancelStream,
        retrieveCurrentSession,
        // WS Handlers
        handleStreamChunk,
        handleStreamEnd,
        handleStreamError,
        handleRoutingResponse,
        handleTitleResponse,
        // Getters/State (Read-only)
        isNodeStreaming,
        isAnyNodeStreaming,
    };
});
