import type { GenerateRequest } from '@/types/chat';
import { SavingStatus } from '@/types/enums';

type StreamChunkCallback = (chunk: string) => void;

interface StreamSession {
    // We have two callbacks here:
    // 1. One for streaming the response in the corresponding block in canvas
    // 2. One for streaming the response in the chat
    chatCallback: StreamChunkCallback | null;
    canvasCallback: StreamChunkCallback | null;
    response: string;
    isStreaming: boolean;
    error: Error | null;
}

// --- Composables ---
const { getGenerateStream } = useAPI();

export const useStreamStore = defineStore('Stream', () => {
    // --- Stores ---
    const { setNeedSave } = useCanvasSaveStore();

    const globalSettingsStore = useSettingsStore();
    const { modelsSettings } = storeToRefs(globalSettingsStore);

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
                response: '',
                isStreaming: false,
                error: null,
            });
        }
        const session = streamSessions.value.get(nodeId);
        if (!session) {
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
    const setChatCallback = (nodeId: string, callback: StreamChunkCallback): void => {
        const session = ensureSession(nodeId);
        session.chatCallback = callback;
    };

    /**
     * Removes the chat callback for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     */
    const removeChatCallback = (nodeId: string): void => {
        const session = ensureSession(nodeId);
        session.chatCallback = null;
    };

    /**
     * Sets the callback function for handling canvas-related stream chunks for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @param callback - The function to call with each stream chunk.
     */
    const setCanvasCallback = (nodeId: string, callback: StreamChunkCallback): void => {
        const session = ensureSession(nodeId);
        session.canvasCallback = callback;
    };

    /**
     * Retrieves the current response for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @returns The current response string.
     */
    const retrieveCurrentResponse = (nodeId: string): string => {
        const session = streamSessions.value.get(nodeId);
        if (!session) {
            console.error(`No session found for node ID: ${nodeId}`);
            return '';
        }
        return session.response;
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
        generateStream: (
            generateRequest: GenerateRequest,
            getCallbacks: () => ((chunk: string) => void)[],
        ) => Promise<void> = getGenerateStream,
    ): Promise<void> => {
        const session = ensureSession(nodeId);

        if (session.isStreaming) {
            console.warn(`Stream for node ID ${nodeId} is already in progress.`);
            return;
        }

        if (!session.chatCallback && !session.canvasCallback) {
            console.error(
                `No chat or canvas callback set for node ID: ${nodeId}. Cannot start streaming.`,
            );
            session.error = new Error('Streaming callbacks not set.');
            return;
        }

        session.isStreaming = true;
        session.error = null;

        generateRequest.reasoning.exclude = modelsSettings.value.excludeReasoning;
        generateRequest.system_prompt = modelsSettings.value.globalSystemPrompt;

        // Set default values for effort and max_tokens if they are null
        if (generateRequest.reasoning.effort === null) {
            generateRequest.reasoning.effort = modelsSettings.value.effort;
        }

        const getStreamCallbacks = (): StreamChunkCallback[] => {
            return [
                session.chatCallback,
                session.canvasCallback,
                (chunk: string): void => {
                    if (chunk === '[START]') {
                        session.response = '';
                        return;
                    }

                    session.response += chunk;
                },
            ].filter((cb): cb is StreamChunkCallback => cb !== null);
        };

        try {
            await generateStream(generateRequest, getStreamCallbacks);

            setNeedSave(SavingStatus.NOT_SAVED);
        } catch (error) {
            console.error(`Error during stream for node ID ${nodeId}:`, error);
            session.error =
                error instanceof Error ? error : new Error('An unknown streaming error occurred');
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
        setChatCallback,
        removeChatCallback,
        setCanvasCallback,
        startStream,
        retrieveCurrentResponse,

        // Getters/State (Read-only)
        isNodeStreaming,
        isAnyNodeStreaming,
    };
});
