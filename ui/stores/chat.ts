import { defineStore } from 'pinia';
import type { Message } from '@/types/graph';
const { getChat } = useAPI();

export const useChatStore = defineStore('Chat', () => {
    const isOpen = ref(false);
    const isFetching = ref(false);
    const messages = ref<Message[]>([]);
    const nload = ref(0);

    const fromNodeId = ref<string>('');
    const currentModel = ref<string>('');

    const isParsed = computed(() => {
        return messages.value.length === nload.value && nload.value > 0;
    });

    const setParsed = () => {
        nload.value += 1;
    };

    const setCurrentModel = (model: string) => {
        currentModel.value = model;
    };

    const openChatFromNodeId = (graphId: string, nodeId: string) => {
        isOpen.value = true;
        isFetching.value = true;
        fromNodeId.value = nodeId;
        getChat(graphId, nodeId)
            .then((response) => {
                messages.value = response;
                isFetching.value = false;
            })
            .catch((error) => {
                console.error('Error fetching chat:', error);
                messages.value = [];
                isFetching.value = false;
            });
    };

    const openChat = () => {
        isOpen.value = true;
        nload.value = 0;
    };

    const closeChat = () => {
        isOpen.value = false;
        nload.value = 0;
    };

    const removeAllMessagesFromIndex = (index: number) => {
        if (index < 0 || index >= messages.value.length) {
            console.error('Index out of bounds');
            return;
        }
        messages.value.splice(index, messages.value.length - index);
    };

    const addMessage = (message: Message) => {
        messages.value.push(message);
    };

    return {
        isOpen,
        isFetching,
        messages,
        isParsed,
        fromNodeId,
        currentModel,
        openChat,
        openChatFromNodeId,
        closeChat,
        setParsed,
        setCurrentModel,
        removeAllMessagesFromIndex,
        addMessage,
    };
});
