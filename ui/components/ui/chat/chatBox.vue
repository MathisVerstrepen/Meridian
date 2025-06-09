<script lang="ts" setup>
import { DEFAULT_NODE_ID } from '@/constants';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';

// --- Stores ---
const chatStore = useChatStore();
const sidebarSelectorStore = useSidebarCanvasStore();
const canvasSaveStore = useCanvasSaveStore();
const streamStore = useStreamStore();
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { openChatId, isFetching, currentModel, isCanvasReady, lastOpenedChatId } =
    storeToRefs(chatStore);
const { isOpen: isSidebarOpen } = storeToRefs(sidebarSelectorStore);
const { generalSettings } = storeToRefs(settingsStore);

// --- Actions/Methods from Stores ---
const {
    removeAllMessagesFromIndex,
    closeChat,
    loadAndOpenChat,
    refreshChat,
    addMessage,
    getLatestMessage,
    getSession,
    removeLastAssistantMessage,
    migrateSessionId,
} = chatStore;
const { saveGraph } = canvasSaveStore;
const {
    setChatCallback,
    startStream,
    isNodeStreaming,
    retrieveCurrentSession,
    removeChatCallback,
} = streamStore;

// --- Routing ---
const route = useRoute();
const router = useRouter();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Composables ---
const { updateNodeModel, updatePromptNodeText, addTextToTextInputNodes, isCanvasEmpty } =
    useGraphChat();

// --- Local State ---
const chatContainer = ref<HTMLElement | null>(null);
const isLockedToBottom = ref(true);
const lastScrollTop = ref(0);
const isStreaming = ref(false);
const streamingSession = ref<StreamSession | null>();
const streamingReply = ref<string>('');
const generationError = ref<string | null>(null);
const nRendered = ref(0);
const session = shallowRef(getSession(openChatId.value || ''));
const currentEditModeIdx = ref<number | null>(null);

// --- Core Logic Functions ---
const scrollToBottom = (behavior: 'smooth' | 'auto' = 'auto') => {
    if (chatContainer.value) {
        chatContainer.value.scrollTo({
            top: chatContainer.value.scrollHeight,
            behavior: behavior,
        });
    }
};

const triggerScroll = (behavior: 'smooth' | 'auto' = 'auto') => {
    if (isLockedToBottom.value) {
        scrollToBottom(behavior);
    }
};

const handleScroll = () => {
    const el = chatContainer.value;
    if (!el) return;

    const currentScrollTop = el.scrollTop;

    if (currentScrollTop < lastScrollTop.value - 10) {
        isLockedToBottom.value = false;
    } else {
        const scrollThreshold = 100;
        const isAtBottom = el.scrollHeight - currentScrollTop - el.clientHeight <= scrollThreshold;
        if (isAtBottom) {
            isLockedToBottom.value = true;
        }
    }

    lastScrollTop.value = Math.max(0, currentScrollTop);
};

const goBackToBottom = () => {
    isLockedToBottom.value = true;
    scrollToBottom('smooth');
};

const addChunk = (chunk: string) => {
    if (chunk === '[START]') {
        isStreaming.value = true;
        streamingReply.value = '';
        generationError.value = null;
        triggerScroll();
        return;
    } else if (chunk === '[END]') {
        isStreaming.value = false;
        saveGraph();
        return;
    }

    streamingReply.value += chunk;
    triggerScroll();
};

const generateNew = async (
    forcedTextToTextNodeId: string | null = null,
    message: string | null = null,
) => {
    let textToTextNodeId: string | undefined;

    // When forcedTextToTextNodeId is provided, it means the message is already
    // in the node and we want to use it as the input for the generation
    if (forcedTextToTextNodeId) {
        const lastestMessage = getLatestMessage();
        if (!lastestMessage?.content) {
            console.warn('No message found, skipping generation.');
            return;
        }

        textToTextNodeId = addTextToTextInputNodes(
            lastestMessage.content,
            openChatId.value,
            forcedTextToTextNodeId,
        );
    }
    // If no forcedTextToTextNodeId is provided, we create a new text-to-text node
    // from the message provided
    else if (message) {
        textToTextNodeId = addTextToTextInputNodes(
            message,
            openChatId.value,
            forcedTextToTextNodeId,
        );

        addMessage({
            role: MessageRoleEnum.user,
            content: message,
            model: currentModel.value,
            node_id: textToTextNodeId || '',
            type: NodeTypeEnum.TEXT_TO_TEXT,
            data: null,
        });
    }

    if (!textToTextNodeId) {
        console.warn('No text-to-text node ID found, skipping message send.');
        return;
    }

    session.value.fromNodeId = textToTextNodeId;

    // When creating a new text-to-text node, we need to change the current
    // node ID to the new one, so we can stream the response to the new node
    if (openChatId.value && openChatId.value !== textToTextNodeId) {
        migrateSessionId(openChatId.value, textToTextNodeId);
        openChatId.value = textToTextNodeId;
    }

    await generate();
};

const generate = async () => {
    if (!session.value.fromNodeId) {
        console.error("Cannot generate response: 'fromNodeId' is missing.");
        generationError.value = 'Cannot generate response: Missing required information.';
        return;
    }

    if (isStreaming.value) {
        console.warn('Generation already in progress.');
        return;
    }

    await saveGraph();

    isLockedToBottom.value = true;

    try {
        streamingSession.value = retrieveCurrentSession(session.value.fromNodeId);

        setChatCallback(session.value.fromNodeId, NodeTypeEnum.TEXT_TO_TEXT, addChunk);

        await startStream(session.value.fromNodeId, NodeTypeEnum.TEXT_TO_TEXT, {
            graph_id: graphId.value,
            node_id: session.value.fromNodeId,
            model: currentModel.value,
            reasoning: {
                effort: null,
                exclude: false,
            },
            system_prompt: '',
        });
    } catch (error) {
        console.error('Error during chat generation or saving:', error);
        generationError.value =
            'An error occurred while generating the response. Please try again.';
    } finally {
        isStreaming.value = false;
        triggerScroll();
    }
};

const regenerate = async (index: number) => {
    if (!session.value.fromNodeId) {
        console.error("Cannot regenerate response: 'fromNodeId' is missing.");
        generationError.value = 'Cannot regenerate response: Missing required information.';
        return;
    }

    removeAllMessagesFromIndex(index);
    updateNodeModel(session.value.fromNodeId, currentModel.value);

    await generate();
};

const closeChatHandler = () => {
    removeChatCallback(openChatId.value || '', NodeTypeEnum.TEXT_TO_TEXT);
    streamingReply.value = '';
    generationError.value = null;
    isStreaming.value = false;
    closeChat();
};

const editMessage = (message: string, index: number, node_id: string) => {
    currentEditModeIdx.value = null;
    updatePromptNodeText(node_id, message);
    saveGraph().then(() => {
        regenerate(index + 1);
    });
};

const handleEditDone = (textContent: string, index: number, nodeId: string) => {
    editMessage(textContent, index, nodeId);
};

// --- Watchers ---
// Watch 1: Scroll when new messages are added (user, streaming assistant, etc.)
watch(
    () => session.value.messages,
    (newMessages, oldMessages) => {
        if (openChatId.value && newMessages.length > (oldMessages?.length ?? 0)) {
            triggerScroll('smooth');
        }
    },
    { deep: true },
);

// Watch 2: Scroll when chat is opened (if messages already exist)
watch(openChatId, (newValue, oldValue) => {
    if (!newValue || newValue === oldValue || oldValue !== null) {
        return;
    }

    session.value = getSession(newValue);
    streamingReply.value = '';
    isLockedToBottom.value = true;

    if (newValue && session.value.messages.length > 0 && !isFetching.value) {
        triggerScroll();
    }

    // If the chat is opened and the fromNodeId is set, we check if the node is streaming
    if (session.value.fromNodeId && isNodeStreaming(session.value.fromNodeId)) {
        // Then we set the streaming state and callback so that the new message can be streamed
        isStreaming.value = true;
        generationError.value = null;

        streamingSession.value = retrieveCurrentSession(session.value.fromNodeId);

        streamingReply.value = streamingSession.value?.response || '';
        setChatCallback(session.value.fromNodeId, NodeTypeEnum.TEXT_TO_TEXT, addChunk);
    }
});

// Watch 3: Scroll specifically after initial load finishes
watch(isFetching, (newValue, oldValue) => {
    if (oldValue === true && newValue === false && openChatId.value) {
        isLockedToBottom.value = true;
        nextTick(() => {
            triggerScroll();
        });
        if (session.value.fromNodeId && isStreaming.value) {
            removeLastAssistantMessage(session.value.fromNodeId);
        }
    }
});

// Watch 4: Scroll when message rendered
watch(nRendered, (newValue) => {
    if (newValue > 0 && openChatId.value) {
        nextTick(() => {
            triggerScroll();
        });
    }
});

// Watch 5: End of stream
watch(isStreaming, async (newValue) => {
    if (!newValue && streamingReply.value.trim()) {
        addMessage({
            role: MessageRoleEnum.assistant,
            content: streamingReply.value,
            model: currentModel.value,
            node_id: null,
            type: streamingSession.value?.type || NodeTypeEnum.TEXT_TO_TEXT,
            data: null,
        });

        // After a parallelization session ends, we need to refetch the chat
        // to get the chat messages of pre-agregation models
        if (streamingSession.value?.type === NodeTypeEnum.PARALLELIZATION) {
            await saveGraph();
            await refreshChat(graphId.value, session.value.fromNodeId);
            session.value = getSession(session.value.fromNodeId || '');
        }

        streamingReply.value = '';
    }
});

// Watch 6: Handle scroll events to attach/detach the scroll event listener safely.
watch(chatContainer, (newEl, oldEl) => {
    if (oldEl) {
        oldEl.removeEventListener('scroll', handleScroll);
    }
    if (newEl) {
        newEl.addEventListener('scroll', handleScroll, { passive: true });
    }
});

// --- Lifecycle Hooks ---
watch(
    () => isCanvasReady.value,
    async (newVal) => {
        if (!newVal) return;
        // If the parameter startStream is set to true, we want to generate a new chat
        // and the prompt message is already in the node
        if (route.query.startStream === 'true') {
            await generateNew(openChatId.value);
        }
        // If we create a new canvas, we set lastOpenedChatId to the default ID so the
        // user can open the chat from the button
        else if (isCanvasEmpty()) {
            lastOpenedChatId.value = DEFAULT_NODE_ID;
            // We open the chat view if the user has set the option to do so
            if (generalSettings.value.openChatViewOnNewCanvas && !route.query.fromHome) {
                openChatId.value = DEFAULT_NODE_ID;
            }
        }

        // Clear url query parameters
        if (route.query.startStream || route.query.fromHome) {
            await router.replace({ query: {} });
        }
    },
);
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute bottom-2 left-[26rem] z-10 flex flex-col items-center
            rounded-2xl border-2 shadow-lg backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'hover:bg-stone-gray/10 h-12 w-12 justify-center hover:cursor-pointer': !openChatId,
            'h-[calc(100%-1rem)] w-[calc(100%-57rem)] justify-start px-4 py-10':
                openChatId && isSidebarOpen,
            'h-[calc(100%-1rem)] w-[calc(100%-30rem)] justify-start px-4 py-10':
                openChatId && !isSidebarOpen,
        }"
    >
        <div
            v-show="openChatId"
            class="relative flex h-full w-full flex-col items-center justify-start"
        >
            <UiChatHeader @close="closeChatHandler"></UiChatHeader>

            <UiChatLoader v-if="isFetching"></UiChatLoader>

            <!-- Chat Messages Area -->
            <div
                v-else
                ref="chatContainer"
                class="text-soft-silk/80 custom_scroll flex h-full flex-col overflow-y-auto px-10"
                aria-live="polite"
            >
                <!-- Message List -->
                <ul class="m-auto flex h-full w-[40vw] flex-col">
                    <li
                        v-for="(message, index) in session.messages"
                        :key="index"
                        class="relative mb-4 w-[90%] rounded-xl px-6 py-3"
                        :class="{
                            'bg-anthracite': message.role === MessageRoleEnum.user,
                            'bg-obsidian ml-[10%]': message.role === MessageRoleEnum.assistant,
                        }"
                    >
                        <UiChatNodeTypeIndicator
                            v-if="message.role === MessageRoleEnum.assistant"
                            :nodeType="message.type"
                        />

                        <UiChatMarkdownRenderer
                            :message="message"
                            :disableHighlight="message.role === MessageRoleEnum.user"
                            :editMode="currentEditModeIdx === index"
                            @rendered="nRendered += 1"
                            @edit-done="
                                handleEditDone($event, index, message.node_id || DEFAULT_NODE_ID)
                            "
                        />

                        <UiChatMessageFooter
                            :message="message"
                            :isStreaming="isStreaming"
                            :isAssistantLastMessage="
                                index === session.messages.length - (isStreaming ? 0 : 1)
                            "
                            :isUserLastMessage="
                                index === session.messages.length - (isStreaming ? 1 : 2)
                            "
                            @regenerate="regenerate(index)"
                            @edit="currentEditModeIdx = index"
                        />
                    </li>

                    <!-- Live Streaming Reply -->
                    <li
                        v-if="(isStreaming || streamingReply) && streamingSession"
                        class="bg-obsidian relative mb-4 ml-[10%] w-[90%] rounded-xl px-6 py-3"
                        aria-live="assertive"
                        aria-atomic="true"
                    >
                        <UiChatNodeTypeIndicator :nodeType="streamingSession.type" />

                        <UiChatMarkdownRenderer
                            :message="{
                                role: MessageRoleEnum.assistant,
                                content: streamingReply,
                                model: currentModel,
                                node_id: session.fromNodeId,
                                type: streamingSession?.type,
                                data: null,
                            }"
                            :editMode="false"
                            :isStreaming="true"
                        />
                    </li>

                    <!-- Error Display -->
                    <div
                        v-if="generationError"
                        class="border-terracotta-clay-dark bg-terracotta-clay/10 text-terracotta-clay my-4 rounded-xl border p-3
                            text-center font-bold"
                    >
                        {{ generationError }}
                    </div>
                </ul>
            </div>

            <button
                v-if="!isLockedToBottom"
                @click="goBackToBottom"
                type="button"
                aria-label="Scroll to bottom"
                class="bg-stone-gray/20 hover:bg-stone-gray/10 absolute bottom-24 z-20 flex h-10 w-10 items-center
                    justify-center rounded-full text-white shadow-lg backdrop-blur transition-all duration-200
                    ease-in-out hover:-translate-y-1 hover:scale-110 hover:cursor-pointer"
            >
                <UiIcon name="FlowbiteChevronDownOutline" class="h-6 w-6" />
            </button>

            <!-- Chat Input Area -->
            <UiChatTextInput
                @trigger-scroll="triggerScroll"
                @generate="
                    (message: string) => {
                        generateNew(null, message);
                    }
                "
                class="max-h-[600px]"
            ></UiChatTextInput>
        </div>

        <!-- Closed State Button -->
        <button
            v-if="!openChatId"
            @click="loadAndOpenChat(graphId, lastOpenedChatId || '')"
            :disabled="!lastOpenedChatId"
            type="button"
            aria-label="Open Chat"
            class="flex h-full w-full items-center justify-center"
            :class="{
                'cursor-not-allowed opacity-20': !lastOpenedChatId,
                'cursor-pointer': lastOpenedChatId,
            }"
        >
            <UiIcon name="MaterialSymbolsAndroidChat" class="text-stone-gray h-6 w-6" />
        </button>
    </div>
</template>

<style scoped>
.custom_scroll {
    scrollbar-width: thin;
    scrollbar-color: var(--color-stone-gray) transparent;
}
.custom_scroll::-webkit-scrollbar {
    width: 8px;
    background-color: transparent;
}
.custom_scroll::-webkit-scrollbar-thumb {
    background-color: var(--color-stone-gray);
    border-radius: 4px;
}
.custom_scroll::-webkit-scrollbar-track {
    background-color: transparent;
}
</style>
