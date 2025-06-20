import type { GenerateRequest } from '@/types/chat';
import type { UsageData } from '@/types/graph';
import { SavingStatus, NodeTypeEnum } from '@/types/enums';

type StreamChunkCallback = (chunk: string) => void;

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
}

// --- Composables ---
const { getGenerateStream } = useAPI();
const { addChunkCallbackBuilder } = useStreamCallbacks();

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
    const ensureSession = (nodeId: string, type: NodeTypeEnum): StreamSession => {
        if (!streamSessions.value.has(nodeId)) {
            streamSessions.value.set(nodeId, {
                chatCallback: null,
                canvasCallback: null,
                response: '',
                usageData: null,
                type: type,
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
    const preStreamSession = (nodeId: string, type: NodeTypeEnum): StreamSession => {
        const session = ensureSession(nodeId, type);

        if (session.isStreaming) {
            console.warn(`Stream session for node ID ${nodeId} is already active.`);
            return session;
        }

        session.isStreaming = true;
        session.error = null;
        session.response = '';
        session.type = type;

        return session;
    };

    /**
     * Starts the generation stream for a specific node.
     * Requires at least one callback (chat or canvas) to be set for the node.
     * @param nodeId - The unique identifier for the stream session.
     * @param generateRequest - The request payload for the generation API.
     */
    const startStream = async (
        nodeId: string,
        type: NodeTypeEnum,
        generateRequest: GenerateRequest,
        generateTitle: boolean = false,
        generateStream: (
            generateRequest: GenerateRequest,
            getCallbacks: () => ((chunk: string) => void)[],
        ) => Promise<void> = getGenerateStream,
    ): Promise<StreamSession | undefined> => {
        const session = preStreamSession(nodeId, type);

        if (!session.chatCallback && !session.canvasCallback) {
            console.error(
                `No chat or canvas callback set for node ID: ${nodeId}. Cannot start streaming.`,
            );
            session.error = new Error('Streaming callbacks not set.');
            return;
        }

        const addChunkCallback = addChunkCallbackBuilder(
            () => (session.response = ''),
            () => {},
            () => {},
            (chunk: string) => (session.response += chunk),
        );

        const getStreamCallbacks = (): StreamChunkCallback[] => {
            return [session.chatCallback, session.canvasCallback, addChunkCallback].filter(
                (cb): cb is StreamChunkCallback => cb !== null,
            );
        };

        try {
            if (generateTitle) {
                const titleRequest = { ...generateRequest };
                titleRequest.title = true;

                // Make two parallel requests: one for the title and one for the main content
                const titleStream = getGenerateStream(titleRequest, () => {
                    return [
                        addChunkCallbackBuilder(
                            () => (session.titleResponse = ''),
                            () => {},
                            () => {},
                            (chunk: string) => (session.titleResponse += chunk),
                        ),
                    ];
                });
                const contentStream = getGenerateStream(generateRequest, getStreamCallbacks);
                await Promise.all([titleStream, contentStream]);
            } else {
                await generateStream(generateRequest, getStreamCallbacks);
            }

            setNeedSave(SavingStatus.NOT_SAVED);
        } catch (error) {
            console.error(`Error during stream for node ID ${nodeId}:`, error);
            session.error =
                error instanceof Error ? error : new Error('An unknown streaming error occurred');
        } finally {
            session.isStreaming = false;
        }

        return session;
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
        preStreamSession,
        startStream,
        retrieveCurrentSession,

        // Getters/State (Read-only)
        isNodeStreaming,
        isAnyNodeStreaming,
    };
});
