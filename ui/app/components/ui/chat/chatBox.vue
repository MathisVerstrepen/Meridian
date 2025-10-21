<script lang="ts" setup>
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import { DEFAULT_NODE_ID } from '@/constants';
import { useChatGenerator } from '@/composables/useChatGenerator';
import { useMessageEditing } from '@/composables/useMessageEditing';

defineProps<{ isGraphNameDefault: boolean }>();

// --- Stores ---
const chatStore = useChatStore();
const sidebarSelectorStore = useSidebarCanvasStore();
const canvasSaveStore = useCanvasSaveStore();
const streamStore = useStreamStore();
const settingsStore = useSettingsStore();

// --- WebSocket Composable ---
const { isConnected, isReconnecting, connect: connectWebSocket } = useWebSocket();

// --- State from Stores (Reactive Refs) ---
const { openChatId, isFetching, isCanvasReady, lastOpenedChatId } = storeToRefs(chatStore);
const { isRightOpen, isLeftOpen } = storeToRefs(sidebarSelectorStore);
const { generalSettings } = storeToRefs(settingsStore);
const { isNodeStreaming } = storeToRefs(streamStore);

// --- Actions/Methods from Stores ---
const { closeChat, loadAndOpenChat, getSession } = chatStore;
const { ensureGraphSaved } = canvasSaveStore;
const { removeChatCallback } = streamStore;

// --- Routing ---
const route = useRoute();
const router = useRouter();
const graphId = computed(() => (route.params.id as string) ?? '');
const isTemporaryGraph = computed(() => route.query.temporary === 'true');

// --- Local State ---
const COLLAPSE_THRESHOLD = 500;
const isRenderingMessages = ref(true);
const renderedMessageCount = ref(0);
const session = shallowRef(getSession(openChatId.value || ''));
const isAtTop = ref(false);
const isAtBottom = ref(true);
const chatContainer: Ref<HTMLElement | null> = ref(null);
const expandedMessages = ref<Set<number>>(new Set());

// --- Composables ---
const { isCanvasEmpty } = useGraphChat();
const { goBackToBottom, scrollToBottom, triggerScroll, handleScroll, isLockedToBottom } =
    useChatScroll(chatContainer);
const { persistGraph } = useAPI();
const graphEvents = useGraphEvents();
const { success, error } = useToast();
const { getTextFromMessage } = useMessage();

// --- Decomposed Logic via Composables ---
const {
    isStreaming,
    streamingSession,
    generationError,
    selectedNodeType,
    generateNew,
    regenerate,
    handleCancelStream,
    restoreStreamingState,
} = useChatGenerator(session, graphId, triggerScroll, goBackToBottom);

const { currentEditModeIdx, handleEditDone } = useMessageEditing(regenerate);

// --- Core Logic Functions ---
const handleMessageRendered = () => {
    renderedMessageCount.value += 1;
};

const toggleMessageExpansion = (index: number) => {
    if (expandedMessages.value.has(index)) {
        expandedMessages.value.delete(index);
    } else {
        expandedMessages.value.add(index);
    }
};

const handleSaveTemporaryGraph = async () => {
    try {
        await persistGraph(graphId.value);
        success('Conversation saved!', { title: 'Success' });
        await router.replace({ query: {} });
        graphEvents.emit('graph-persisted', { graphId: graphId.value });
    } catch (err) {
        console.error('Failed to save temporary graph:', err);
        error('Could not save conversation. Please try again.', {
            title: 'Save Error',
        });
    }
};

const closeChatHandler = () => {
    if (openChatId.value) {
        removeChatCallback(openChatId.value, NodeTypeEnum.TEXT_TO_TEXT);
    }
    generationError.value = null;
    renderedMessageCount.value = 0;
    closeChat();
};

const branchFromId = async (nodeId: string) => {
    await loadAndOpenChat(graphId.value, nodeId);
    session.value = getSession(nodeId);
    setTimeout(() => {
        goBackToBottom();
    }, 10);
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && openChatId.value && !isTemporaryGraph.value) {
        closeChatHandler();
    }
};

const updateScrollState = () => {
    if (!chatContainer.value) {
        isAtTop.value = true;
        isAtBottom.value = true;
        return;
    }
    const { scrollTop, scrollHeight, clientHeight } = chatContainer.value;
    const threshold = 2;
    isAtTop.value = scrollTop <= threshold;
    isAtBottom.value = scrollHeight - scrollTop <= clientHeight + threshold;
};

// --- Watchers ---
// Watch 1: Scroll when new messages are added
watch(
    () => session.value.messages,
    (newMessages, oldMessages) => {
        if (openChatId.value && newMessages.length > (oldMessages?.length ?? 0)) {
            triggerScroll('smooth');
        }
        nextTick(updateScrollState);
    },
    { deep: true, immediate: true },
);

// Watch 2: Track fetching state to manage session and streaming
watch(isFetching, (newValue, oldValue) => {
    if (oldValue === true && newValue === false && openChatId.value) {
        session.value = getSession(openChatId.value);
        isLockedToBottom.value = true;

        if (session.value.fromNodeId && isNodeStreaming.value(session.value.fromNodeId)) {
            restoreStreamingState();
            renderedMessageCount.value++;
        }
    }
    if (newValue === true) {
        isRenderingMessages.value = true;
    }
});

// Watch 3: Track when all messages are finished rendering
watch(renderedMessageCount, (count) => {
    if (count > 0 && count >= (session.value?.messages?.length || 0)) {
        isRenderingMessages.value = false;
        nextTick(() => {
            scrollToBottom();
        });
    }
});

// Watch 4: End of stream
watch(isStreaming, async (newValue, oldValue) => {
    if (oldValue === true && !newValue) {
        const lastMessage = session.value.messages[session.value.messages.length - 1];
        if (lastMessage?.content[0]?.text) {
            await ensureGraphSaved();
        }
        triggerScroll();
    }
});

// Watch 5: Handle scroll events
watch(chatContainer, (newEl, oldEl) => {
    if (oldEl) {
        oldEl.removeEventListener('scroll', handleScroll);
        oldEl.removeEventListener('wheel', handleScroll);
        oldEl.removeEventListener('scroll', updateScrollState);
    }
    if (newEl) {
        newEl.addEventListener('wheel', handleScroll, { passive: true });
        newEl.addEventListener('scroll', updateScrollState, { passive: true });
        nextTick(updateScrollState);
    }
});

// Watch 6: Canvas Ready Lifecycle
watch(
    () => isCanvasReady.value,
    async (newVal) => {
        if (!newVal) return;
        if (route.query.startStream === 'true' && openChatId.value) {
            await generateNew(openChatId.value);
        } else if (isCanvasEmpty()) {
            lastOpenedChatId.value = DEFAULT_NODE_ID;
            if (
                (generalSettings.value.openChatViewOnNewCanvas && !route.query.fromHome) ||
                isTemporaryGraph.value
            ) {
                openChatId.value = DEFAULT_NODE_ID;
            }
            session.value = getSession(DEFAULT_NODE_ID);
        }

        if ((route.query.startStream || route.query.fromHome) && !isTemporaryGraph.value) {
            await router.replace({ query: {} });
        } else if (isTemporaryGraph.value && openChatId.value) {
            await router.replace({ query: { temporary: 'true' } });
        }
    },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    document.addEventListener('keydown', handleKeyDown);
    connectWebSocket();
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
    <div
        class="dark:bg-anthracite/75 bg-stone-gray/20 border-stone-gray/10 absolute bottom-2
            left-[26rem] z-20 flex flex-col items-center rounded-2xl border-2 shadow-lg
            backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'hover:bg-stone-gray/10 h-12 w-12 justify-center hover:cursor-pointer': !openChatId,
            'h-[calc(100%-1rem)] justify-start px-4 pb-10': openChatId,
            'w-[calc(100%-57rem)]': openChatId && isRightOpen && isLeftOpen,
            'w-[calc(100%-30rem)]': openChatId && !isRightOpen && isLeftOpen,
            'w-[calc(100%-35rem)]': openChatId && isRightOpen && !isLeftOpen,
            'w-[calc(100%-8rem)]': openChatId && !isRightOpen && !isLeftOpen,
            '!left-[4rem]': !isLeftOpen,
        }"
    >
        <Teleport to="body">
            <div
                v-if="!isConnected"
                class="bg-terracotta-clay/20 border-terracotta-clay/40 absolute bottom-0 left-1/2
                    z-50 w-96 -translate-x-1/2 rounded-t-xl border p-2 text-center text-sm
                    font-semibold text-white backdrop-blur-lg"
            >
                {{ isReconnecting ? 'Connection lost. Reconnecting...' : 'Connecting...' }}
            </div>
        </Teleport>

        <div
            v-show="openChatId"
            class="relative flex h-full w-full flex-col items-center justify-start"
        >
            <UiChatHeader
                :is-temporary="isTemporaryGraph"
                :is-empty="session.messages.length === 0"
                @close="closeChatHandler"
                @save="handleSaveTemporaryGraph"
            />

            <div
                v-if="
                    isRenderingMessages &&
                    session.messages.length === 0 &&
                    !isStreaming &&
                    !isFetching
                "
                class="text-soft-silk/60 flex h-full items-center justify-center text-center"
            >
                No messages yet. Start the conversation!
            </div>

            <UiChatUtilsLoader
                v-if="isRenderingMessages && (session.messages.length > 0 || isFetching)"
            />

            <!-- Chat Messages Area -->
            <div
                ref="chatContainer"
                class="text-soft-silk/80 custom_scroll stable-scrollbar-gutter flex w-full grow
                    flex-col overflow-y-auto px-10"
                aria-live="polite"
                :class="{
                    'h-0 opacity-0': isRenderingMessages,
                    'h-full opacity-100': !isRenderingMessages,
                }"
            >
                <!-- Message List -->
                <ul class="m-auto flex h-full w-[80%] max-w-[800px] flex-col">
                    <li
                        v-for="(message, index) in session.messages"
                        :key="index"
                        :data-message-index="index"
                        class="relative mt-5 mb-2 w-[90%] rounded-xl px-6 py-3 backdrop-blur-2xl"
                        :class="{
                            'dark:bg-anthracite bg-anthracite/50':
                                message.role === MessageRoleEnum.user,
                            'dark:bg-obsidian bg-soft-silk/75 ml-[10%]':
                                message.role === MessageRoleEnum.assistant,
                        }"
                        @dblclick="
                            graphEvents.emit('open-node-data', {
                                selectedNodeId: message.node_id || null,
                            })
                        "
                    >
                        <UiChatNodeTypeIndicator
                            v-if="message.role === MessageRoleEnum.assistant"
                            :node-type="message.type"
                        />

                        <UiChatMarkdownRenderer
                            :message="message"
                            :edit-mode="currentEditModeIdx === index"
                            :is-streaming="isStreaming && index === session.messages.length - 1"
                            :is-collapsed="
                                message.role === MessageRoleEnum.user &&
                                !expandedMessages.has(index) &&
                                (getTextFromMessage(message) || '').length > COLLAPSE_THRESHOLD
                            "
                            @rendered="handleMessageRendered"
                            @trigger-scroll="triggerScroll"
                            @edit-done="
                                (nodeId, textContent) => handleEditDone(textContent, index, nodeId)
                            "
                        />

                        <UiChatMessageFooter
                            :message="message"
                            :is-streaming="isStreaming"
                            :is-assistant-last-message="index === session.messages.length - 1"
                            :is-user-last-message="index === session.messages.length - 2"
                            :is-collapsible="
                                message.role === MessageRoleEnum.user &&
                                (getTextFromMessage(message) || '').length > COLLAPSE_THRESHOLD
                            "
                            :is-collapsed="
                                message.role === MessageRoleEnum.user &&
                                !expandedMessages.has(index) &&
                                (getTextFromMessage(message) || '').length > COLLAPSE_THRESHOLD
                            "
                            @regenerate="regenerate(index)"
                            @edit="currentEditModeIdx = index"
                            @branch="branchFromId(message.node_id || DEFAULT_NODE_ID)"
                            @toggle-collapse="toggleMessageExpansion(index)"
                        />
                    </li>

                    <!-- Error Display -->
                    <div
                        v-if="generationError"
                        class="border-terracotta-clay-dark bg-terracotta-clay/10
                            text-terracotta-clay my-4 rounded-xl border p-3 text-center font-bold"
                    >
                        {{ generationError }}
                    </div>

                    <div class="h-3 shrink-0" />
                </ul>
            </div>

            <!-- Chat Input Area -->
            <UiChatTextInput
                v-if="openChatId"
                :is-locked-to-bottom="isLockedToBottom"
                :is-streaming="isStreaming"
                :is-disabled="!isConnected"
                :node-type="streamingSession?.type || NodeTypeEnum.STREAMING"
                from="chat"
                class="!max-h-[600px]"
                @trigger-scroll="triggerScroll"
                @generate="
                    (message: string, files: FileSystemObject[]) => {
                        generateNew(null, message, files);
                    }
                "
                @go-back-to-bottom="goBackToBottom"
                @cancel-stream="handleCancelStream"
                @select-node-type="
                    (newType) => {
                        selectedNodeType = newType;
                    }
                "
            />

            <UiChatUtilsMessageTeleport
                v-if="session.messages.length > 0 && chatContainer"
                class="left-8"
                :role-to-find="MessageRoleEnum.user"
                :messages="session.messages"
                :chat-container="chatContainer"
                :is-at-top="isAtTop"
                :is-at-bottom="isAtBottom"
                shortcut-modifier="CTRL"
                @teleport="isLockedToBottom = false"
            />
            <UiChatUtilsMessageTeleport
                v-if="session.messages.length > 0 && chatContainer"
                class="right-8"
                :role-to-find="MessageRoleEnum.assistant"
                :messages="session.messages"
                :chat-container="chatContainer"
                :is-at-top="isAtTop"
                :is-at-bottom="isAtBottom"
                shortcut-modifier="ALT"
                @teleport="isLockedToBottom = false"
            />
        </div>

        <!-- Closed State Button -->
        <ClientOnly>
            <button
                v-if="!openChatId"
                :disabled="!lastOpenedChatId"
                type="button"
                aria-label="Open Chat"
                class="flex h-full w-full items-center justify-center"
                :class="{
                    'cursor-not-allowed opacity-20': !lastOpenedChatId,
                    'cursor-pointer': lastOpenedChatId,
                }"
                @click="loadAndOpenChat(graphId, lastOpenedChatId || '')"
            >
                <UiIcon name="MaterialSymbolsAndroidChat" class="text-stone-gray h-6 w-6" />
            </button>
        </ClientOnly>
    </div>
</template>

<style scoped></style>
