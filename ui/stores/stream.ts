import type { GenerateRequest } from '@/types/chat';
import { SavingStatus } from '@/types/enums';
import { ref } from 'vue';

interface StreamSession {
    // We have two callbacks here:
    // 1. One for streaming the response in the corresponding block in canvas
    // 2. One for streaming the response in the chat
    chatCallback: (chunk: string) => void;
    canvasCallback: (chunk: string) => void;
    isStreaming: boolean;
}

export const useStreamStore = defineStore('Stream', () => {
    const { getGenerateStream } = useAPI();
    const { setNeedSave } = useCanvasSaveStore();

    const streamSessions = ref<Map<string, StreamSession>>(new Map());

    const startStream = async (
        node_id: string,
        generateRequest: GenerateRequest,
    ) => {
        const session = streamSessions.value.get(node_id);

        if (!session) {
            console.error(`No stream session found for node ID: ${node_id}`);
            return;
        }

        if (
            session.chatCallback === undefined ||
            session.canvasCallback === undefined
        ) {
            console.error('Callbacks are not set. Cannot start streaming.');
            return;
        }

        session.isStreaming = true;
        await getGenerateStream(generateRequest, [
            session.chatCallback,
            session.canvasCallback,
        ]);
        setNeedSave(SavingStatus.NOT_SAVED);
        session.isStreaming = false;
    };

    const setChatCallback = (
        node_id: string,
        callback: (chunk: string) => void,
    ) => {
        const session = streamSessions.value.get(node_id);
        if (session) {
            session.chatCallback = callback;
        } else {
            streamSessions.value.set(node_id, {
                chatCallback: callback,
                canvasCallback: () => {},
                isStreaming: false,
            });
        }
    };

    const setCanvasCallback = (
        node_id: string,
        callback: (chunk: string) => void,
    ) => {
        const session = streamSessions.value.get(node_id);
        if (session) {
            session.canvasCallback = callback;
        } else {
            streamSessions.value.set(node_id, {
                chatCallback: () => {},
                canvasCallback: callback,
                isStreaming: false,
            });
        }
    };

    return {
        startStream,
        setChatCallback,
        setCanvasCallback,
    };
});
