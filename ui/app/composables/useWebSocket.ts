import { v4 as uuidv4 } from 'uuid';
import type { ImageGenerationJob } from '@/types/imagePlayground';

// --- Reactive State (Singleton) ---
const state = reactive({
    ws: null as WebSocket | null,
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
        const message = JSON.parse(event.data);
        const { type, node_id, payload, model_id } = message;
        const streamStore = useStreamStore();

        if (!type || (!node_id && !NODE_OPTIONAL_MESSAGE_TYPES.has(type))) {
            console.warn('Received WebSocket message without type or node_id:', message);
            return;
        }

        switch (type) {
            case 'stream_chunk':
                streamStore.handleStreamChunk(node_id, payload, model_id);
                break;
            case 'stream_end':
                streamStore.handleStreamEnd(node_id, payload, model_id);
                break;
            case 'stream_error':
                streamStore.handleStreamError(node_id, payload);
                break;
            case 'tool_question_error':
                streamStore.handleToolQuestionError(node_id, payload);
                break;
            case 'routing_response':
                streamStore.handleRoutingResponse(node_id, payload);
                break;
            case 'title_response':
                streamStore.handleTitleResponse(node_id, payload);
                break;
            case 'usage_data_update':
                streamStore.handleUsageDataUpdate(node_id, payload);
                break;
            case 'node_data_update':
                handleNodeDataUpdate(message?.graph_id, node_id, payload);
                break;
            case 'node_data_replace':
                replaceNodeData(message?.graph_id, node_id, payload);
                break;
            case 'image_generation_job_update':
                useImagePlaygroundStore().handleJobUpdate(payload as ImageGenerationJob);
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

const sendMessage = (message: object): boolean => {
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
