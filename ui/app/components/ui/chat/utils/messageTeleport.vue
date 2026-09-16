<script lang="ts" setup>
import { MessageRoleEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

const props = defineProps<{
    messages: Message[];
    chatContainer: HTMLElement | null;
}>();

const emit = defineEmits<{
    teleport: [];
}>();

const scrollEndTimer = ref<ReturnType<typeof setTimeout> | null>(null);
const activePreviewIndex = ref<number | null>(null);
const { getTextFromMessageFast } = useMessage();

const PREVIEW_LENGTH = 80;
const TELEPORT_TOP_INSET = 16;
const FALLBACK_PREVIEW = 'User message';
const NODE_ID_MARKER_REGEX = /--- Node ID: [a-f0-9-]+ ---/g;

const getPreview = (message: Message): string => {
    const normalizedText = getTextFromMessageFast(message)
        .replace(NODE_ID_MARKER_REGEX, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    if (!normalizedText) return FALLBACK_PREVIEW;
    if (normalizedText.length <= PREVIEW_LENGTH) return normalizedText;
    return `${normalizedText.slice(0, PREVIEW_LENGTH).trimEnd()}…`;
};

const userMessages = computed(() =>
    props.messages
        .map((message, index) => ({ message, index }))
        .filter(({ message }) => message.role === MessageRoleEnum.user)
        .map(({ message, index }) => ({
            index,
            preview: getPreview(message),
        })),
);

const scrollToIndex = (index: number) => {
    if (!props.chatContainer) return;
    const el = props.chatContainer.querySelector<HTMLElement>(`[data-message-index="${index}"]`);
    if (el) {
        const container = props.chatContainer;

        const highlight = () => {
            el.classList.add('highlight-teleport');
            el.addEventListener('animationend', () => el.classList.remove('highlight-teleport'), {
                once: true,
            });
        };

        const scrollEndListener = () => {
            if (scrollEndTimer.value) clearTimeout(scrollEndTimer.value);
            scrollEndTimer.value = setTimeout(() => {
                highlight();
                container.removeEventListener('scroll', scrollEndListener);
            }, 100);
        };

        // Check if already inset from the top to handle cases where no scroll event will be fired.
        const desiredScrollTop = Math.max(0, el.offsetTop - TELEPORT_TOP_INSET);

        if (Math.abs(container.scrollTop - desiredScrollTop) < 2) {
            highlight();
            return;
        }

        container.addEventListener('scroll', scrollEndListener);
        container.scrollTo({ top: desiredScrollTop, behavior: 'smooth' });
    }
};

const teleport = (index: number) => {
    emit('teleport');
    scrollToIndex(index);
};

onUnmounted(() => {
    if (scrollEndTimer.value) clearTimeout(scrollEndTimer.value);
});
</script>

<template>
    <nav
        v-if="userMessages.length > 0"
        aria-label="User message navigator"
        class="absolute top-1/2 left-2 z-20 flex -translate-y-1/2 flex-col items-start py-2"
    >
        <div
            v-for="(entry, position) in userMessages"
            :key="entry.index"
            class="relative flex items-center"
        >
            <button
                type="button"
                :aria-label="`Go to user message ${position + 1}: ${entry.preview}`"
                class="group flex h-3 w-8 cursor-pointer items-center rounded-sm focus-visible:outline-2
                    focus-visible:outline-offset-2 focus-visible:outline-soft-silk/70"
                @mouseenter="activePreviewIndex = entry.index"
                @mouseleave="activePreviewIndex = null"
                @focus="activePreviewIndex = entry.index"
                @blur="activePreviewIndex = null"
                @click="teleport(entry.index)"
            >
                <span
                    aria-hidden="true"
                    class="bg-soft-silk/35 group-hover:bg-soft-silk/80
                        group-focus-visible:bg-soft-silk/80 h-0.5 w-3 rounded-full transition-all
                        duration-150 group-hover:w-6 group-focus-visible:w-6"
                />
            </button>
            <div
                v-if="activePreviewIndex === entry.index"
                class="bg-obsidian/95 text-soft-silk pointer-events-none absolute top-1/2 left-full
                    ml-3 w-max max-w-72 -translate-y-1/2 rounded-lg px-3 py-2 text-xs leading-5
                    font-medium whitespace-normal shadow-lg backdrop-blur-sm"
            >
                {{ entry.preview }}
            </div>
        </div>
    </nav>
</template>

<style>
@keyframes highlight-anim {
    0% {
        outline: 2px solid color-mix(in oklab, var(--color-soft-silk) 20%, transparent);
        box-shadow: 0 0 15px solid color-mix(in oklab, var(--color-soft-silk) 40%, transparent);
    }
    100% {
        outline: 2px solid transparent;
        box-shadow: none;
    }
}
.highlight-teleport {
    animation: highlight-anim 1s ease-out;
    outline-offset: 2px;
}
</style>
