<script lang="ts" setup>
import { MessageRoleEnum } from '@/types/enums';

const chatStore = useChatStore();
const { isOpen, isFetching, messages, isParsed, fromNodeId, currentModel } = storeToRefs(chatStore);
const { removeAllMessagesFromIndex, closeChat, openChat, addMessage } = chatStore;
const sidebarSelectorStore = useSidebarSelectorStore();
const { isOpen: isSidebarOpen } = storeToRefs(sidebarSelectorStore);
const { saveGraph } = useCanvasSaveStore();

const route = useRoute();
const { id } = route.params as { id: string };

const chatContainer = ref<HTMLElement | null>(null);
const isStreaming = ref(false);
const streamingReply = ref<string>('');

const triggerScroll = () => {
    if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight + 100;
    }
};

const addChunk = (chunk: string) => {
    if (chunk === '[START]') {
        streamingReply.value = '';
        return;
    }
    streamingReply.value += chunk;
    triggerScroll();
};

const { setChatCallback, startStream } = useStreamStore();

const generate = async () => {
    if (!fromNodeId.value) return;

    isStreaming.value = true;
    streamingReply.value = '';

    setChatCallback(fromNodeId.value, addChunk);

    await startStream(fromNodeId.value, {
        graph_id: id,
        node_id: fromNodeId.value,
        model: currentModel.value || '',
    });

    isStreaming.value = false;

    addMessage({
        role: MessageRoleEnum.assistant,
        content: streamingReply.value,
    });
    streamingReply.value = '';

    await saveGraph();
};

const regenerate = async (index: number) => {
    removeAllMessagesFromIndex(index);
    setChatCallback(fromNodeId.value || '', addChunk);
    await generate();
};

watch(
    () => isParsed.value,
    (newValue) => {
        if (newValue) {
            nextTick(() => {
                triggerScroll();
            });
        }
    },
);

watch(
    () => isOpen.value,
    (newValue) => {
        if (newValue) {
            nextTick(() => {
                streamingReply.value = '';
            });
        }
    },
);
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute bottom-2 left-[26rem] z-10 flex flex-col items-center
            rounded-2xl border-2 shadow-lg backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'hover:bg-stone-gray/10 h-12 w-12 justify-center hover:cursor-pointer': !isOpen,
            'h-[calc(100%-1rem)] w-[calc(100%-57rem)] justify-start px-4 py-10':
                isOpen && isSidebarOpen,
            'h-[calc(100%-1rem)] w-[calc(100%-30rem)] justify-start px-4 py-10':
                isOpen && !isSidebarOpen,
        }"
    >
        <div
            v-show="isOpen"
            class="relative flex h-full w-full flex-col items-center justify-start"
        >
            <h1 class="mb-8 flex items-center space-x-3">
                <UiIcon name="MaterialSymbolsAndroidChat" class="text-stone-gray h-6 w-6" />
                <span class="text-stone-gray font-outfit text-2xl font-bold">Chat</span>
            </h1>

            <button
                class="hover:bg-stone-gray/10 absolute top-0 right-7 flex items-center justify-center rounded-full p-1
                    transition-colors duration-200 ease-in-out"
            >
                <UiIcon
                    name="MaterialSymbolsClose"
                    class="text-stone-gray h-6 w-6"
                    @click="closeChat"
                />
            </button>

            <div
                class="text-soft-silk/80 flex h-full items-center justify-center"
                v-if="isFetching"
            >
                <div class="flex flex-col items-center gap-4">
                    <div
                        class="border-soft-silk/80 h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
                    ></div>
                    <span class="z-10">Retrieving chat...</span>
                </div>
            </div>

            <div
                class="text-soft-silk/80 custom_scroll flex h-full overflow-y-auto px-10"
                v-else
                ref="chatContainer"
            >
                <ul class="m-auto flex h-full w-[50rem] flex-col">
                    <li
                        v-for="(message, index) in messages"
                        :key="index"
                        class="mb-4 w-[90%] rounded-xl px-6 py-3"
                        :class="{
                            'bg-anthracite': message.role === 'user',
                            'bg-obsidian ml-[10%]': message.role === 'assistant',
                        }"
                    >
                        <UiChatMarkdownRenderer :content="message.content" />

                        <div
                            v-if="message.role === 'assistant'"
                            class="bg-anthracite mt-2 mr-0 ml-auto flex w-fit items-center justify-center rounded-full"
                        >
                            <UiIcon
                                name="MaterialSymbolsRefreshRounded"
                                class="text-stone-gray bg-anthracite hover:bg-stone-gray/20 h-7 w-10 rounded-full px-2 py-1
                                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                                @click="regenerate(index)"
                            />
                        </div>
                    </li>

                    <div
                        v-if="isStreaming || streamingReply != ''"
                        class="bg-obsidian mb-4 ml-[10%] w-[90%] rounded-xl px-6 py-3"
                    >
                        <UiChatMarkdownRenderer :content="streamingReply" />
                    </div>
                </ul>
            </div>

            <UiChatTextInput @trigger-scroll="triggerScroll" @generate="generate"></UiChatTextInput>
        </div>

        <button
            v-show="!isOpen"
            class="flex h-full w-full items-center justify-center"
            @click="openChat"
        >
            <UiIcon
                name="MaterialSymbolsAndroidChat"
                class="text-stone-gray h-6 w-6"
                @click="openChat"
            />
        </button>
    </div>
</template>

<style scoped>
.custom_scroll {
    scrollbar-color: var(--color-stone-gray) transparent;
}
.custom_scroll::-webkit-scrollbar {
    background-color: transparent;
}
</style>
