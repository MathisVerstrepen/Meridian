<script lang="ts" setup>
const emit = defineEmits(['update:reply', 'update:doneAction']);

// --- Props ---
const props = defineProps<{
    reply: string;
    readonly: boolean;
    color?: 'olive-grove' | 'terracotta-clay' | 'slate-blue' | 'sunbaked-sand' | null;
    placeholder: string;
    autoscroll: boolean;
}>();

// --- Local State ---
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const isError = ref(false);

// --- Computed Properties ---
const displayValue = computed(() => {
    return props.reply.replace(/^\[ERROR\]/, '').replace(/\[!ERROR\]$/, '');
});

// --- Core Logic Functions ---
function handleInput(event: Event) {
    const target = event.target as HTMLTextAreaElement;
    emit('update:reply', target.value);
}

function handleKeydown(event: KeyboardEvent) {
    if (event.key === ' ' && event.shiftKey) {
        return;
    }

    if (event.key === 'Enter' && event.ctrlKey) {
        event.preventDefault();
        emit('update:doneAction', true);
    }
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

watch(
    () => props.reply,
    (newValue) => {
        if (isError.value !== /\[ERROR\].*\[!ERROR\]/s.test(newValue)) {
            isError.value = !isError.value;
        }
    },
    { immediate: true, flush: 'post' },
);
</script>

<template>
    <div class="relative flex h-full w-full flex-col overflow-hidden">
        <div
            v-if="isError"
            class="mb-2 flex w-full shrink-0 flex-grow items-center justify-center gap-2 overflow-hidden rounded-2xl
                bg-[#612020] p-2"
        >
            <UiIcon
                v-if="color !== undefined"
                name="MaterialSymbolsErrorCircleRounded"
                class="h-8 w-8 shrink-0 text-[#ffb3b3]"
            />
            <p class="w-full text-xs text-[#ffb3b3]">{{ displayValue }}</p>
        </div>

        <textarea
            ref="textareaRef"
            :value="!isError ? displayValue : ''"
            @input="handleInput"
            @keydown.stop="handleKeydown"
            :readonly="readonly"
            class="dark:text-soft-silk text-anthracite nodrag nowheel hide-scrollbar h-full w-full flex-grow
                resize-none rounded-2xl px-3 py-2 text-sm caret-current focus:ring-0 focus:outline-none"
            :placeholder="placeholder"
            :class="{
                'bg-[#545d48]': color === 'olive-grove',
                'bg-terracotta-clay-dark': color === 'terracotta-clay',
                'bg-[#49545f]': color === 'slate-blue',
                'bg-sunbaked-sand-dark !text-obsidian': color === 'sunbaked-sand',
            }"
            @focusout="emit('update:doneAction', false)"
        ></textarea>
    </div>
</template>

<style scoped></style>
