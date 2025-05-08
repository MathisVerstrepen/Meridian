<script lang="ts" setup>
const emit = defineEmits(['triggerScroll', 'generate']);

// --- Stores ---
const chatStore = useChatStore();

// --- State from Stores (Reactive Refs) ---
const { currentModel } = storeToRefs(chatStore);

// --- Actions/Methods from Stores ---
const { addMessage } = chatStore;

// --- Local State ---
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const message = ref<string>('');
const isEmpty = ref(true);

// --- Core Logic Functions ---
const onInput = () => {
    const el = textareaRef.value;
    if (!el) return;
    emit('triggerScroll');
    message.value = el.innerText.trim();
    isEmpty.value = message.value.length === 0;
};

const sendMessage = async () => {
    emit('generate', message.value);

    message.value = '';
    isEmpty.value = true;
    const el = textareaRef.value;
    if (!el) return;
    el.innerText = '';
};
</script>

<template>
    <div
        class="bg-obsidian mt-6 flex h-fit w-[80%] max-w-[70rem] items-end justify-center rounded-3xl px-2 py-2
            shadow"
    >
        <div
            contenteditable
            ref="textareaRef"
            class="contenteditable text-soft-silk/80 field-sizing-content h-fit max-h-full w-full resize-none
                overflow-hidden overflow-y-auto border-none bg-transparent px-4 py-3 outline-none"
            data-placeholder="Type your message here..."
            :class="{ 'show-placeholder': isEmpty }"
            @input="onInput"
            @keydown.enter.exact.prevent="sendMessage"
            autofocus
        ></div>
        <button
            class="bg-stone-gray hover:bg-stone-gray/80 flex h-12 w-12 items-center justify-center rounded-2xl shadow
                transition duration-200 ease-in-out hover:cursor-pointer"
            @click="sendMessage"
        >
            <UiIcon name="IconamoonSendFill" class="text-obsidian h-6 w-6" />
        </button>
    </div>
</template>

<style scoped>
.contenteditable {
    position: relative;
}

.contenteditable.show-placeholder::before {
    content: attr(data-placeholder);
    position: absolute;
    left: 1rem;
    top: 0.75rem;
    color: var(--color-soft-silk);
    opacity: 0.6;
    pointer-events: none;
}

.contenteditable:not(.show-placeholder)::before {
    content: none;
}
</style>
