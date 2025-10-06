import { v4 as uuidv4 } from 'uuid';

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

// --- Private Functions ---
const handleOpen = () => {
    console.log('WebSocket connection established.');
    state.isConnected = true;
    state.isConnecting = false;
    state.isReconnecting = false;
    state.reconnectAttempts = 0;
};

const handleMessage = (event: MessageEvent) => {
    try {
        const message = JSON.parse(event.data);
        const { type, node_id, payload, model_id } = message;
        const streamStore = useStreamStore();

        if (!type || !node_id) {
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
            case 'routing_response':
                streamStore.handleRoutingResponse(node_id, payload);
                break;
            case 'title_response':
                streamStore.handleTitleResponse(node_id, payload);
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
    if (state.ws || state.isConnecting) {
        return;
    }

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

    try {
        state.ws = new WebSocket(wsUrl);
        state.ws.onopen = handleOpen;
        state.ws.onmessage = handleMessage;
        state.ws.onclose = handleClose;
        state.ws.onerror = handleError;
    } catch (error) {
        console.error('Failed to create WebSocket:', error);
        state.isConnecting = false;
    }
};

const disconnect = () => {
    if (state.ws) {
        state.reconnectAttempts = MAX_RECONNECT_ATTEMPTS;
        state.ws.close(1000, 'User disconnected');
        state.ws = null;
    }
};

const sendMessage = (message: object) => {
    if (state.ws && state.isConnected) {
        state.ws.send(JSON.stringify(message));
    } else {
        console.error('WebSocket is not connected. Message not sent:', message);
    }
};

export const useWebSocket = () => {
    return {
        ...toRefs(state),
        connect,
        disconnect,
        sendMessage,
    };
};
