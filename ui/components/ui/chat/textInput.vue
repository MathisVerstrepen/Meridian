<script lang="ts" setup>
const emit = defineEmits(['triggerScroll']);
const message = ref<string>('');
const isEmpty = ref(true);

const { addTextToTextInputNodes } = useGraphStore();

const textareaRef = ref<HTMLTextAreaElement | null>(null);

const onInput = () => {
    const el = textareaRef.value;
    if (!el) return;
    emit('triggerScroll');
    message.value = el.innerText.trim();
    isEmpty.value = message.value.length === 0;
};

const sendChat = () => {
    addTextToTextInputNodes(message.value);
};
</script>

<template>
    <div
        class="bg-obsidian mt-5 flex h-fit w-[80%] items-end justify-center rounded-3xl px-2 py-2 shadow"
    >
        <div
            contenteditable
            ref="textareaRef"
            class="contenteditable text-soft-silk/80 field-sizing-content h-fit max-h-[600px] w-full resize-none
                overflow-hidden overflow-y-auto border-none bg-transparent px-4 py-3 outline-none"
            data-placeholder="Type your message here..."
            :class="{ 'show-placeholder': isEmpty }"
            @input="onInput"
        ></div>
        <button
            class="bg-stone-gray hover:bg-stone-gray/80 flex h-12 w-12 items-center justify-center rounded-2xl shadow
                transition duration-200 ease-in-out hover:cursor-pointer"
            @click="sendChat"
        >
            <Icon
                name="material-symbols:send-rounded"
                style="color: var(--color-obsidian); height: 1.5rem; width: 1.5rem"
            />
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
