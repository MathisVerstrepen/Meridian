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
const { getGenerateStream } = useAPI();
const { addChunkCallbackBuilder } = useStreamCallbacks();

export const useStreamStore = defineStore('Stream', () => {
    // --- Stores ---
    const { setNeedSave } = useCanvasSaveStore();
    const { error } = useToast();

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
                type: type,
                isStreaming: false,
                error: null,
                isBackground: isBackground,
            });
        }
        const session = streamSessions.value.get(nodeId);
        if (!session) {
            error(`Session for node ID ${nodeId} not found after creation.`, {
                title: 'Stream Error',
            });
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
            error(`No session found for node ID: ${nodeId}`, {
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
            getCallbacks: () => ((chunk: string) => Promise<void>)[],
        ) => Promise<void> = getGenerateStream,
        isBackground: boolean = false,
    ): Promise<StreamSession | undefined> => {
        const session = preStreamSession(nodeId, type, isBackground);

        if (!isBackground && !session.chatCallback && !session.canvasCallback) {
            console.error(
                `No chat or canvas callback set for node ID: ${nodeId}. Cannot start streaming.`,
            );
            error(`No chat or canvas callback set for node ID: ${nodeId}.`, {
                title: 'Stream Error',
            });
            session.error = new Error('Streaming callbacks not set.');
            return;
        }

        const addChunkCallback = addChunkCallbackBuilder(
            () => (session.response = ''),
            () => {},
            (chunk: string) => (session.response += chunk),
        );

        const getStreamCallbacks = (): StreamChunkCallback[] => {
            if (isBackground) {
                return [addChunkCallback];
            }
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
        } catch (err) {
            console.error(`Error during stream for node ID ${nodeId}:`, err);
            error(`Failed to start stream for node ID ${nodeId}: ${(err as Error).message}`, {
                title: 'Stream Error',
            });
            session.error =
                err instanceof Error ? err : new Error('An unknown streaming error occurred');
        } finally {
            session.isStreaming = false;
        }

        return session;
    };

    /**
     * Cancels the stream for a specific node.
     * @param nodeId - The unique identifier for the stream session.
     * @returns True if the stream was successfully cancelled, false otherwise.
     */
    const cancelStream = async (nodeId: string): Promise<boolean> => {
        const session = streamSessions.value.get(nodeId);
        if (!session) return false;

        const route = useRoute();
        const graphId = route.params.id as string;

        const cancelled = await useAPI().cancelStream(graphId, nodeId);
        if (cancelled) {
            session.isStreaming = false;
            session.error = new Error('Stream cancelled by user');
        }

        return cancelled;
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

        // Getters/State (Read-only)
        isNodeStreaming,
        isAnyNodeStreaming,
    };
});
