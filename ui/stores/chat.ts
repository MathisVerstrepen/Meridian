import { defineStore } from 'pinia';
import type { Message } from '@/types/graph';

export const useChatStore = defineStore('Chat', () => {
    const isOpen = ref(false);
    const isLoading = ref(false);
    const messages = ref<Message[]>([]);

    const { getChat } = useAPI();

    const openChat = () => {
        isOpen.value = true;
    };

    const openChatFromNodeId = (graphId: string, nodeId: string) => {
        isOpen.value = true;
        isLoading.value = true;
        getChat(graphId, nodeId)
            .then((response) => {
                messages.value = response;
                isLoading.value = false;
            })
            .catch((error) => {
                console.error('Error fetching chat:', error);
                messages.value = [];
                isLoading.value = false;
            });
    };

    const closeChat = () => {
        isOpen.value = false;
    };

    return {
        isOpen,
        isLoading,
        messages,
        openChat,
        openChatFromNodeId,
        closeChat,
    };
});
