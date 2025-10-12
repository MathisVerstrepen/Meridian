<script lang="ts" setup>
import { MessageRoleEnum } from '@/types/enums';
import type { Message } from '@/types/graph';

// --- Props ---
const props = defineProps<{
    roleToFind: MessageRoleEnum;
    messages: Message[];
    chatContainer: HTMLElement | null;
    isAtTop: boolean;
    isAtBottom: boolean;
    shortcutModifier: 'ALT' | 'CTRL';
}>();

// --- Emits ---
const emit = defineEmits(['teleport']);

// --- Local State ---
const scrollEndTimer = ref<ReturnType<typeof setTimeout> | null>(null);
const isMac = ref(false);

// --- Computed ---
const roleName = computed(() => (props.roleToFind === MessageRoleEnum.user ? 'user' : 'assistant'));
const modifierSymbol = computed(() => {
    if (props.shortcutModifier === 'CTRL') {
        return isMac.value ? '⌘' : 'CTRL';
    }
    if (props.shortcutModifier === 'ALT') {
        return isMac.value ? '⌥' : 'ALT';
    }
    return props.shortcutModifier;
});
const relevantIndices = computed(() =>
    props.messages
        .map((msg, index) => (msg.role === props.roleToFind ? index : -1))
        .filter((index) => index !== -1),
);

// --- Methods ---
const findCurrentMessageIndex = (): number => {
    if (!props.chatContainer) return -1;
    const { scrollTop } = props.chatContainer;

    // Find the first message that is at least partially in view from the top
    for (let i = 0; i < props.messages.length; i++) {
        const el = props.chatContainer.querySelector<HTMLElement>(`[data-message-index="${i}"]`);
        if (el && el.offsetTop + el.offsetHeight > scrollTop) {
            return i;
        }
    }
    return props.messages.length - 1;
};

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

        // Check if already centered to handle cases where no scroll event will be fired.
        const elCenter = el.offsetTop + el.offsetHeight / 2;
        const desiredScrollTop = elCenter - container.clientHeight / 2;

        if (Math.abs(container.scrollTop - desiredScrollTop) < 2) {
            highlight();
            return;
        }

        container.addEventListener('scroll', scrollEndListener);
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
};

const teleport = (direction: 'up' | 'down') => {
    if (relevantIndices.value.length === 0) return;

    emit('teleport');

    const currentIndex = findCurrentMessageIndex();
    let targetIndex = -1;

    if (direction === 'up') {
        if (props.isAtTop) return;
        // Find the last relevant index that is strictly smaller than the current index.
        const candidates = relevantIndices.value.filter((i) => i < currentIndex);
        if (candidates.length > 0) {
            targetIndex = candidates[candidates.length - 1];
        }
    } else {
        if (props.isAtBottom) return;
        // Find the first relevant index that is strictly larger than the current index.
        const candidates = relevantIndices.value.filter((i) => i - 1 > currentIndex);
        if (candidates.length > 0) {
            targetIndex = candidates[0];
        }
    }

    if (targetIndex !== -1) {
        scrollToIndex(targetIndex);
    }
};

const handleKeyDown = (e: KeyboardEvent) => {
    if (e.shiftKey) return;

    const isMacPlatform = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    let modifierMatch = false;

    if (props.shortcutModifier === 'CTRL') {
        if (isMacPlatform) {
            if (e.metaKey && !e.ctrlKey && !e.altKey) {
                modifierMatch = true;
            }
        } else {
            if (e.ctrlKey && !e.metaKey && !e.altKey) {
                modifierMatch = true;
            }
        }
    } else if (props.shortcutModifier === 'ALT') {
        if (e.altKey && !e.ctrlKey && !e.metaKey) {
            modifierMatch = true;
        }
    }

    if (modifierMatch) {
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            teleport('up');
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            teleport('down');
        }
    }
};

onMounted(() => {
    isMac.value = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    document.addEventListener('keydown', handleKeyDown);
});

// --- Lifecycle ---
onMounted(() => {
    document.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
    <div
        class="bg-obsidian/50 text-soft-silk/60 absolute bottom-20 flex flex-col rounded-xl p-1 backdrop-blur-sm"
    >
        <button
            :title="`Previous ${roleName} message (${modifierSymbol} + ↑)`"
            :disabled="isAtTop"
            class="hover:bg-soft-silk/5 rounded-[8px] bg-transparent p-1 duration-200 ease-in-out"
            :class="{ 'cursor-pointer': !isAtTop, 'cursor-not-allowed opacity-50': isAtTop }"
            @click="teleport('up')"
        >
            <UiIcon name="LineMdChevronSmallUp" class="h-8 w-8" />
        </button>
        <button
            :title="`Next ${roleName} message (${modifierSymbol} + ↓)`"
            :disabled="isAtBottom"
            class="hover:bg-soft-silk/5 rounded-[8px] bg-transparent p-1 duration-200 ease-in-out"
            :class="{ 'cursor-pointer': !isAtBottom, 'cursor-not-allowed opacity-50': isAtBottom }"
            @click="teleport('down')"
        >
            <UiIcon name="LineMdChevronSmallUp" class="h-8 w-8 rotate-180" />
        </button>
    </div>
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
