import { defineStore } from 'pinia';
import type { Message } from '@/types/graph';
const { getChat } = useAPI();

export const useChatStore = defineStore('Chat', () => {
    const isOpen = ref(false);
    const isFetching = ref(false);
    const messages = ref<Message[]>([]);
    const nload = ref(0);

    const fromNodeId = ref<string | null>(null);

    const isParsed = computed(() => {
        return messages.value.length === nload.value && nload.value > 0;
    });

    const setParsed = () => {
        nload.value += 1;
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

    return {
        isOpen,
        isFetching,
        messages,
        isParsed,
        fromNodeId,
        openChat,
        openChatFromNodeId,
        closeChat,
        setParsed,
    };
});
