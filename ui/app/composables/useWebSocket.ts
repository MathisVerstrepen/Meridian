import { v4 as uuidv4 } from 'uuid';
import type {
    ImageGenerationJob,
    ImagePlaygroundJobStatus,
    ImagePlaygroundMediaType,
} from '@/types/imagePlayground';

// --- Reactive State (Singleton) ---
interface WebSocketState {
    ws: WebSocket | null;
    isConnected: boolean;
    isConnecting: boolean;
    isReconnecting: boolean;
    reconnectAttempts: number;
    clientId: string;
}

interface ToolQuestionErrorPayload {
    tool_call_id?: string;
    message?: string;
}

const state = reactive<WebSocketState>({
    ws: null,
    isConnected: false,
    isConnecting: false,
    isReconnecting: false,
    reconnectAttempts: 0,
    clientId: uuidv4(),
});

const MAX_RECONNECT_ATTEMPTS = 10;
const RECONNECT_INTERVAL_BASE = 1000; // 1 second
const NODE_OPTIONAL_MESSAGE_TYPES = new Set([
    'image_generation_job_update',
    'tool_question_error',
]);
let connectionPromise: Promise<void> | null = null;

const IMAGE_JOB_STATUSES: ImagePlaygroundJobStatus[] = [
    'pending',
    'processing',
    'retrying',
    'completed',
    'failed',
    'cancelled',
];
const IMAGE_MEDIA_TYPES: ImagePlaygroundMediaType[] = ['image', 'video'];
const isOptionalString = (value: JsonValue) =>
    value === undefined || value === null || isRuntimeString(value);
const isOptionalNumber = (value: JsonValue) =>
    value === undefined || value === null || isRuntimeNumber(value);

const isImageGenerationJob = (value: JsonValue): value is ImageGenerationJob & JsonObject =>
    isJsonObject(value) &&
    isRuntimeString(value.id) &&
    isRuntimeString(value.batch_id) &&
    isRuntimeString(value.status) &&
    IMAGE_JOB_STATUSES.some((status) => status === value.status) &&
    isRuntimeString(value.prompt) &&
    isRuntimeString(value.effective_prompt) &&
    isRuntimeString(value.model) &&
    isRuntimeString(value.media_type) &&
    IMAGE_MEDIA_TYPES.some((mediaType) => mediaType === value.media_type) &&
    isRuntimeString(value.aspect_ratio) &&
    isRuntimeString(value.resolution) &&
    isOptionalNumber(value.duration) &&
    isRuntimeBoolean(value.generate_audio) &&
    isOptionalNumber(value.actual_width) &&
    isOptionalNumber(value.actual_height) &&
    isOptionalString(value.actual_aspect_ratio) &&
    isOptionalString(value.style_preset) &&
    Array.isArray(value.source_image_ids) &&
    value.source_image_ids.every(isRuntimeString) &&
    isOptionalString(value.file_id) &&
    isOptionalString(value.error) &&
    isRuntimeNumber(value.attempts) &&
    isRuntimeNumber(value.max_attempts) &&
    (value.is_preview === undefined || isRuntimeBoolean(value.is_preview)) &&
    isRuntimeString(value.created_at) &&
    isRuntimeString(value.updated_at) &&
    isOptionalString(value.completed_at);

// --- Private Functions ---
const handleOpen = () => {
    console.log('WebSocket connection established.');
    state.isConnected = true;
    state.isConnecting = false;
    state.isReconnecting = false;
    state.reconnectAttempts = 0;
};

const handleMessage = (event: MessageEvent) => {
    const { handleNodeDataUpdate, replaceNodeData } = useGraphActions();

    try {
        if (!isRuntimeString(event.data)) throw new TypeError('WebSocket message is not text');
        const message: JsonValue = JSON.parse(event.data);
        if (!isJsonObject(message)) throw new TypeError('WebSocket message is not an object');
        const { type, node_id, payload, model_id } = message;
        const streamStore = useStreamStore();

        if (
            !isRuntimeString(type) ||
            (!isRuntimeString(node_id) && !NODE_OPTIONAL_MESSAGE_TYPES.has(type))
        ) {
            console.warn('Received WebSocket message without type or node_id:', message);
            return;
        }
        const nodeId = runtimeString(node_id);
        const modelId = isRuntimeString(model_id) ? model_id : undefined;

        switch (type) {
            case 'stream_chunk':
                if (isRuntimeString(payload)) streamStore.handleStreamChunk(nodeId, payload, modelId);
                break;
            case 'stream_end':
                streamStore.handleStreamEnd(
                    nodeId,
                    {
                        refresh_tool_usage:
                            isJsonObject(payload) && payload.refresh_tool_usage === true,
                    },
                    modelId,
                );
                break;
            case 'stream_error':
                streamStore.handleStreamError(nodeId, {
                    message: runtimeErrorMessage(payload) ?? 'Unknown stream error',
                });
                break;
            case 'tool_question_error': {
                const toolError: ToolQuestionErrorPayload = {};
                if (isJsonObject(payload) && isRuntimeString(payload.tool_call_id)) {
                    toolError.tool_call_id = payload.tool_call_id;
                }
                if (isJsonObject(payload) && isRuntimeString(payload.message)) {
                    toolError.message = payload.message;
                }
                streamStore.handleToolQuestionError(nodeId, toolError);
                break;
            }
            case 'routing_response':
                streamStore.handleRoutingResponse(nodeId, payload);
                break;
            case 'title_response':
                if (isJsonObject(payload) && isRuntimeString(payload.title)) {
                    streamStore.handleTitleResponse(nodeId, { title: payload.title });
                }
                break;
            case 'usage_data_update': {
                const usageData = parseUsageData(payload);
                if (usageData) streamStore.handleUsageDataUpdate(nodeId, usageData);
                break;
            }
            case 'node_data_update':
                if (isJsonObject(payload)) {
                    handleNodeDataUpdate(runtimeString(message.graph_id), nodeId, payload);
                }
                break;
            case 'node_data_replace':
                if (isJsonObject(payload) || Array.isArray(payload)) {
                    replaceNodeData(runtimeString(message.graph_id), nodeId, payload);
                }
                break;
            case 'image_generation_job_update':
                if (isImageGenerationJob(payload)) {
                    useImagePlaygroundStore().handleJobUpdate(payload);
                } else {
                    console.warn('Received invalid image generation job update:', payload);
                }
                break;
            default:
                console.warn('Received unknown WebSocket message type:', type);
        }
    } catch (error) {
        console.error('Failed to parse WebSocket message:', event.data, error);
    }
};

const handleClose = (event: CloseEvent) => {
    console.log(`WebSocket connection closed: Code ${event.code}, Reason: ${event.reason}`);
    state.isConnected = false;
    state.isConnecting = false;
    state.ws = null;

    if (event.code === 1000 || event.code === 1008) {
        state.reconnectAttempts = MAX_RECONNECT_ATTEMPTS;
        return;
    }

    if (state.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        state.isReconnecting = true;
        const delay = RECONNECT_INTERVAL_BASE * Math.pow(2, state.reconnectAttempts);
        console.log(`Attempting to reconnect in ${delay / 1000} seconds...`);
        setTimeout(() => {
            state.reconnectAttempts++;
            connect();
        }, delay);
    } else {
        console.error('Max WebSocket reconnection attempts reached.');
        state.isReconnecting = false;
    }
};

const handleError = (event: Event) => {
    console.error('WebSocket error:', event);
    state.isConnecting = false;
};

// --- Public API ---
const connect = async () => {
    if (state.isConnected) {
        return;
    }
    if (connectionPromise) return connectionPromise;

    connectionPromise = (async () => {
        const { getWebSocketToken } = useAPI();
        let token: string | null = null;

        try {
            const response = await getWebSocketToken();
            token = response.token;
        } catch (error) {
            console.error('Failed to get WebSocket token, aborting connection.', error);
            // The apiFetch wrapper in useAPI handles redirection on critical auth failures.
            return;
        }

        if (!token) {
            console.error('Cannot connect WebSocket: No auth token retrieved.');
            return;
        }

        state.isConnecting = true;
        state.isReconnecting = state.reconnectAttempts > 0;

        const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl.replace(/^http/, 'ws');
        const wsUrl = `${API_BASE_URL}/ws/chat/${state.clientId}?token=${token}`;

        await new Promise<void>((resolve) => {
            try {
                const socket = new WebSocket(wsUrl);
                state.ws = socket;
                socket.onopen = () => {
                    handleOpen();
                    resolve();
                };
                socket.onmessage = handleMessage;
                socket.onclose = (event) => {
                    handleClose(event);
                    resolve();
                };
                socket.onerror = (event) => {
                    handleError(event);
                    resolve();
                };
            } catch (error) {
                console.error('Failed to create WebSocket:', error);
                state.isConnecting = false;
                resolve();
            }
        });
    })().finally(() => {
        connectionPromise = null;
    });

    return connectionPromise;
};

const disconnect = () => {
    if (state.ws) {
        state.reconnectAttempts = MAX_RECONNECT_ATTEMPTS;
        state.ws.close(1000, 'User disconnected');
        state.ws = null;
    }
};

const sendMessage = <Message extends object>(message: Message): boolean => {
    if (state.ws && state.isConnected) {
        try {
            state.ws.send(JSON.stringify(message));
            return true;
        } catch (error) {
            console.error('Failed to send WebSocket message:', message, error);
            return false;
        }
    }

    console.error('WebSocket is not connected. Message not sent:', message);
    return false;
};

export const useWebSocket = () => {
    return {
        ...toRefs(state),
        connect,
        disconnect,
        sendMessage,
    };
};
