<script lang="ts" setup>
const chatStore = useChatStore();
const { isOpen, isFetching, messages, isParsed } = storeToRefs(chatStore);
const sidebarSelectorStore = useSidebarSelectorStore();
const { isOpen: isSidebarOpen } = storeToRefs(sidebarSelectorStore);

const chatContainer = ref<HTMLElement | null>(null);

const triggerScroll = () => {
    if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
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
                    @click="chatStore.closeChat()"
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
                <ul class="m-auto flex h-full max-w-[50rem] min-w-[20rem] flex-col">
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
                    </li>
                </ul>
            </div>

            <UiChatTextInput @trigger-scroll="triggerScroll"></UiChatTextInput>
        </div>

        <button
            v-show="!isOpen"
            class="flex h-full w-full items-center justify-center"
            @click="chatStore.openChat()"
        >
            <UiIcon
                name="MaterialSymbolsAndroidChat"
                class="text-stone-gray h-6 w-6"
                @click="chatStore.openChat()"
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
