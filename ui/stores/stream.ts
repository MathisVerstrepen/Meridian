import type { GenerateRequest } from '@/types/chat';
import { SavingStatus } from '@/types/enums';

type StreamChunkCallback = (chunk: string) => void;

interface StreamSession {
    // We have two callbacks here:
    // 1. One for streaming the response in the corresponding block in canvas
    // 2. One for streaming the response in the chat
    chatCallback: StreamChunkCallback | null;
    canvasCallback: StreamChunkCallback | null;
    isStreaming: boolean;
    error: Error | null;
}

export const useStreamStore = defineStore('Stream', () => {
    // --- Dependencies ---
    const { getGenerateStream } = useAPI();
    const { setNeedSave } = useCanvasSaveStore();

    // --- State ---
    const streamSessions = ref<Map<string, StreamSession>>(new Map());

    // --- Private Helper Functions ---

    /**
     * Ensures a session exists for the given node_id, creating one if necessary.
     * @param nodeId - The unique identifier for the stream session.
     * @returns The existing or newly created StreamSession.
     */
    const ensureSession = (nodeId: string): StreamSession => {
        if (!streamSessions.value.has(nodeId)) {
            streamSessions.value.set(nodeId, {
                chatCallback: null,
                canvasCallback: null,
                isStreaming: false,
                error: null,
            });
        }
        const session = streamSessions.value.get(nodeId);
        if (!session) {
            throw new Error(
                `Failed to get or create session for node ID: ${nodeId}`,
            );
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
        callback: StreamChunkCallback,
    ): void => {
        const session = ensureSession(nodeId);
        session.chatCallback = callback;
    };

    /**
     * Sets the callback function for handling canvas-related stream chunks for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param callback - The function to call with each stream chunk.
     */
    const setCanvasCallback = (
        nodeId: string,
        callback: StreamChunkCallback,
    ): void => {
        const session = ensureSession(nodeId);
        session.canvasCallback = callback;
    };

    /**
     * Starts the generation stream for a specific node.
     * Requires at least one callback (chat or canvas) to be set for the node.
     * @param nodeId - The unique identifier for the stream session.
     * @param generateRequest - The request payload for the generation API.
     */
    const startStream = async (
        nodeId: string,
        generateRequest: GenerateRequest,
    ): Promise<void> => {
        const session = ensureSession(nodeId);

        if (session.isStreaming) {
            console.warn(
                `Stream for node ID ${nodeId} is already in progress.`,
            );
            return;
        }

        if (!session.chatCallback && !session.canvasCallback) {
            console.error(
                `No chat or canvas callback set for node ID: ${nodeId}. Cannot start streaming.`,
            );
            session.error = new Error('Streaming callbacks not set.');
            return;
        }

        const callbacks = [session.chatCallback, session.canvasCallback].filter(
            (cb): cb is StreamChunkCallback => cb !== null,
        );

        session.isStreaming = true;
        session.error = null;

        try {
            await getGenerateStream(generateRequest, callbacks);

            setNeedSave(SavingStatus.NOT_SAVED);
        } catch (error) {
            console.error(`Error during stream for node ID ${nodeId}:`, error);
            session.error =
                error instanceof Error
                    ? error
                    : new Error('An unknown streaming error occurred');
        } finally {
            session.isStreaming = false;
        }
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
     * Gets the last error encountered for a specific node's stream.
     * @param nodeId - The unique identifier for the stream session.
     * @returns The Error object if an error occurred, null otherwise.
     */
    const getNodeStreamError = computed(
        () =>
            (nodeId: string): Error | null => {
                return streamSessions.value.get(nodeId)?.error ?? null;
            },
    );

    return {
        // Actions
        setChatCallback,
        setCanvasCallback,
        startStream,

        // Getters/State (Read-only access recommended)
        isNodeStreaming,
        getNodeStreamError,
    };
});
