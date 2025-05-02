<script lang="ts" setup>
import { MessageRoleEnum } from '@/types/enums';

// --- Stores ---
const chatStore = useChatStore();
const sidebarSelectorStore = useSidebarSelectorStore();
const canvasSaveStore = useCanvasSaveStore();
const streamStore = useStreamStore();

// --- State from Stores (Reactive Refs) ---
const {
    isOpen: isChatOpen,
    isFetching,
    messages,
    fromNodeId,
    currentModel,
} = storeToRefs(chatStore);
const { isOpen: isSidebarOpen } = storeToRefs(sidebarSelectorStore);

// --- Actions/Methods from Stores ---
const { removeAllMessagesFromIndex, closeChat, openChat, addMessage } = chatStore;
const { saveGraph } = canvasSaveStore;
const { setChatCallback, startStream } = streamStore;

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Local State ---
const chatContainer = ref<HTMLElement | null>(null);
const isStreaming = ref(false);
const streamingReply = ref<string>('');
const generationError = ref<string | null>(null);
const nRendered = ref(0);

// --- Core Logic Functions ---
const triggerScroll = (behavior: 'smooth' | 'auto' = 'auto') => {
    nextTick(() => {
        if (chatContainer.value) {
            chatContainer.value.scrollTo({
                top: chatContainer.value.scrollHeight,
                behavior: behavior,
            });
        }
    });
};

const addChunk = (chunk: string) => {
    if (chunk === '[START]') {
        streamingReply.value = '';
        return;
    }

    streamingReply.value += chunk;
    nextTick(triggerScroll);
};

const generate = async () => {
    if (!fromNodeId.value) {
        console.error("Cannot generate response: 'fromNodeId' is missing.");
        generationError.value = 'Cannot generate response: Missing required information.';
        return;
    }
    if (isStreaming.value) {
        console.warn('Generation already in progress.');
        return;
    }

    isStreaming.value = true;
    streamingReply.value = '';
    generationError.value = null;

    try {
        setChatCallback(fromNodeId.value, addChunk);

        await startStream(fromNodeId.value, {
            graph_id: graphId.value,
            node_id: fromNodeId.value,
            model: currentModel.value || '',
        });

        if (streamingReply.value.trim()) {
            addMessage({
                role: MessageRoleEnum.assistant,
                content: streamingReply.value,
                model: currentModel.value,
            });
        }

        await saveGraph();
    } catch (error) {
        console.error('Error during chat generation or saving:', error);
        generationError.value =
            'An error occurred while generating the response. Please try again.';
    } finally {
        isStreaming.value = false;
        streamingReply.value = '';
        nextTick(triggerScroll);
    }
};

const regenerate = async (index: number) => {
    if (!fromNodeId.value) {
        console.error("Cannot regenerate response: 'fromNodeId' is missing.");
        generationError.value = 'Cannot regenerate response: Missing required information.';
        return;
    }
    removeAllMessagesFromIndex(index);
    await generate();
};

const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
        console.log('Text copied to clipboard:', text);
    });
};

// --- Watchers ---
// Watch 1: Scroll when new messages are added (user, streaming assistant, etc.)
watch(
    messages,
    (newMessages, oldMessages) => {
        if (isChatOpen.value && newMessages.length > (oldMessages?.length ?? 0)) {
            triggerScroll('smooth');
        }
    },
    { deep: true },
);

// Watch 2: Scroll specifically after initial load finishes
watch(isFetching, (newValue, oldValue) => {
    if (oldValue === true && newValue === false && isChatOpen.value) {
        triggerScroll('auto');
    }
});

// Watch 3: Scroll when chat is opened (if messages already exist)
watch(isChatOpen, (newValue) => {
    if (newValue && messages.value.length > 0 && !isFetching.value) {
        triggerScroll('auto');
    }
});

// Watch 4: Scroll when message rendered
watch(nRendered, (newValue) => {
    if (newValue > 0 && isChatOpen.value) {
        triggerScroll('auto');
    }
});

// --- Lifecycle Hooks ---
onMounted(() => {
    nextTick(triggerScroll);
});
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute bottom-2 left-[26rem] z-10 flex flex-col items-center
            rounded-2xl border-2 shadow-lg backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'hover:bg-stone-gray/10 h-12 w-12 justify-center hover:cursor-pointer': !isChatOpen,
            'h-[calc(100%-1rem)] w-[calc(100%-57rem)] justify-start px-4 py-10':
                isChatOpen && isSidebarOpen,
            'h-[calc(100%-1rem)] w-[calc(100%-30rem)] justify-start px-4 py-10':
                isChatOpen && !isSidebarOpen,
        }"
    >
        <div
            v-show="isChatOpen"
            class="relative flex h-full w-full flex-col items-center justify-start"
        >
            <!-- Header -->
            <h1 class="mb-8 flex items-center space-x-3">
                <UiIcon name="MaterialSymbolsAndroidChat" class="text-stone-gray h-6 w-6" />
                <span class="text-stone-gray font-outfit text-2xl font-bold">Chat</span>
            </h1>

            <!-- Close Button -->
            <button
                class="hover:bg-stone-gray/10 absolute top-0 right-7 flex items-center justify-center rounded-full p-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
            >
                <UiIcon
                    name="MaterialSymbolsClose"
                    class="text-stone-gray h-6 w-6"
                    @click="closeChat"
                />
            </button>

            <!-- Loading State -->
            <div
                v-if="isFetching"
                class="text-soft-silk/80 flex h-full items-center justify-center"
            >
                <div class="flex flex-col items-center gap-4">
                    <div
                        class="border-soft-silk/80 h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
                    ></div>
                    <span class="z-10">Retrieving chat...</span>
                </div>
            </div>

            <!-- Chat Messages Area -->
            <div
                v-else
                ref="chatContainer"
                class="text-soft-silk/80 custom_scroll flex h-full overflow-y-auto px-10"
                aria-live="polite"
            >
                <!-- Error Display -->
                <div
                    v-if="generationError"
                    class="my-4 rounded border border-red-400 bg-red-100 p-3 text-center text-red-700"
                >
                    {{ generationError }}
                </div>

                <!-- Message List -->
                <ul class="m-auto flex h-full max-w-[50rem] flex-col">
                    <li
                        v-for="(message, index) in messages"
                        :key="index"
                        class="mb-4 w-[90%] rounded-xl px-6 py-3"
                        :class="{
                            'bg-anthracite': message.role === 'user',
                            'bg-obsidian ml-[10%]': message.role === 'assistant',
                        }"
                    >
                        <UiChatMarkdownRenderer
                            :content="message.content"
                            @rendered="nRendered += 1"
                            :disableHighlight="message.role === MessageRoleEnum.user"
                        />

                        <div class="mt-2 flex items-center justify-between">
                            <!-- Used Model -->
                            <div
                                v-if="message.role === MessageRoleEnum.assistant && !isStreaming"
                                class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-1 text-xs font-bold"
                            >
                                {{ message.model }}
                            </div>

                            <!-- Regenerate Button -->
                            <div
                                v-if="!isStreaming"
                                class="flex w-fit items-center justify-center rounded-full"
                                :class="{
                                    'bg-obsidian': message.role === MessageRoleEnum.user,
                                    'bg-anthracite/50': message.role === MessageRoleEnum.assistant,
                                }"
                            >
                                <button
                                    @click="copyToClipboard(message.content)"
                                    type="button"
                                    aria-label="Copy this response"
                                    class="text-stone-gray flex items-center justify-center rounded-full px-2 py-1
                                        transition-colors duration-200 ease-in-out hover:cursor-pointer"
                                    :class="{
                                        'hover:bg-anthracite/50': message.role === MessageRoleEnum.user,
                                        'hover:bg-anthracite':
                                            message.role === MessageRoleEnum.assistant,
                                    }"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsContentCopyOutlineRounded"
                                        class="h-5 w-5"
                                    />
                                </button>
                                <button
                                    @click="regenerate(index)"
                                    type="button"
                                    aria-label="Regenerate this response"
                                    class="hover:bg-anthracite text-stone-gray flex items-center justify-center rounded-full px-2 py-1
                                        transition-colors duration-200 ease-in-out hover:cursor-pointer"
                                    v-if="
                                        message.role === MessageRoleEnum.assistant &&
                                        index === messages.length - 1
                                    "
                                >
                                    <UiIcon name="MaterialSymbolsRefreshRounded" class="h-5 w-5" />
                                </button>
                            </div>
                        </div>
                    </li>

                    <!-- Live Streaming Reply -->
                    <div
                        v-if="isStreaming || streamingReply"
                        class="bg-obsidian mb-4 ml-[10%] w-[90%] rounded-xl px-6 py-3"
                        aria-live="assertive"
                        aria-atomic="true"
                    >
                        <UiChatMarkdownRenderer :content="streamingReply || '...'" />
                    </div>
                </ul>
            </div>

            <!-- Chat Input Area -->
            <UiChatTextInput @trigger-scroll="triggerScroll" @generate="generate"></UiChatTextInput>
        </div>

        <!-- Closed State Button -->
        <button
            v-if="!isChatOpen"
            @click="openChat"
            type="button"
            aria-label="Open Chat"
            class="flex h-full w-full items-center justify-center hover:cursor-pointer"
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
