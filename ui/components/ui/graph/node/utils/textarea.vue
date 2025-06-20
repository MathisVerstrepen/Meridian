<script lang="ts" setup>
const emit = defineEmits(['update:reply']);

// --- Props ---
const props = defineProps<{
    reply: string;
    readonly: boolean;
    color?: 'olive-grove' | 'terracotta-clay' | 'slate-blue' | null;
    placeholder: string;
    autoscroll: boolean;
    doneAction?: () => void;
}>();

// --- Local State ---
const textareaRef = ref<HTMLTextAreaElement | null>(null);

// --- Core Logic Functions ---
function handleInput(event: Event) {
    const target = event.target as HTMLTextAreaElement;
    emit('update:reply', target.value);
}

// --- Watchers ---
if (props.autoscroll) {
    watch(
        () => props.reply,
        async () => {
            await nextTick();

            if (textareaRef.value) {
                textareaRef.value.scrollTop = textareaRef.value.scrollHeight;
            }
        },
    );
}
</script>

<template>
    <div class="relative h-full w-full">
        <textarea
            ref="textareaRef"
            :value="reply"
            @input="handleInput"
            :readonly="readonly"
            class="text-soft-silk nodrag nowheel hide-scrollbar h-full w-full flex-grow resize-none rounded-2xl px-3
                py-2 text-sm focus:ring-0 focus:outline-none"
            :placeholder="placeholder"
            :class="{
                'bg-[#545d48]': color === 'olive-grove',
                'bg-terracotta-clay-dark': color === 'terracotta-clay',
                'bg-[#49545f]': color === 'slate-blue',
            }"
            @focusout="doneAction"
            @keypress.enter.prevent="doneAction"
        ></textarea>
    </div>
</template>

<style scoped></style>
