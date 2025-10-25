<script lang="ts" setup>
const emit = defineEmits(['triggerScroll']);

defineProps<{
    thinkingHtml: string;
    isStreaming?: boolean;
}>();

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { generalSettings } = storeToRefs(globalSettingsStore);

// --- Core Logic Functions ---
const handleToggle = async (isOpen: boolean) => {
    if (!isOpen) {
        await nextTick();
        emit('triggerScroll');
    }
};
</script>

<template>
    <HeadlessDisclosure
        v-slot="{ open: isThinkingOpen }"
        :default-open="generalSettings.alwaysThinkingDisclosures"
    >
        <HeadlessDisclosureButton
            class="dark:hover:text-soft-silk/60 hover:text-anthracite/20 dark:text-soft-silk/80
                text-obsidian flex h-fit w-fit cursor-pointer items-center gap-2 rounded-lg py-2
                transition-colors duration-200 ease-in-out mb-2"
            @click="handleToggle(isThinkingOpen)"
        >
            <div
                class="flex shrink-0 items-center gap-2"
                :class="{ 'breathing-glow': isStreaming }"
            >
                <div v-if="isStreaming" class="MdiLightbulbOutline" />

                <UiIcon v-else name="MdiLightbulbOutline" class="h-4 w-4" />

                <span v-if="isStreaming" class="thinking-dots text-sm font-bold">Thinking</span>
                <span v-else class="text-sm font-bold">Thoughts</span>
            </div>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="h-4 w-4 transition-transform duration-200"
                :class="isThinkingOpen ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>
        <div
            class="col-span-2 col-start-1 row-start-2 flex w-full items-stretch gap-4
                transition-opacity duration-200"
            :class="{
                'mb-0 h-0 w-0 overflow-hidden opacity-0': !isThinkingOpen,
                'h-full opacity-100': isThinkingOpen,
            }"
        >
            <div class="dark:bg-anthracite bg-anthracite/20 mb-4 w-1 shrink-0 rounded" />
            <div
                class="prose prose-invert h-full w-full max-w-none pr-5 pb-4 opacity-75"
                :class="{
                    'hide-code-scrollbar': isStreaming,
                }"
                v-html="thinkingHtml"
            />
        </div>
    </HeadlessDisclosure>
</template>

<style scoped>
.thinking-dots::after {
    display: inline-block;
    animation: dots 1.4s infinite;
    content: '.';
    width: 1.2em;
    text-align: left;
}

@keyframes dots {
    0% {
        content: '.';
    }
    33% {
        content: '..';
    }
    66% {
        content: '...';
    }
}

.MdiLightbulbOutline {
    display: inline-block;
    width: 16px;
    height: 16px;
    -webkit-mask: url(/assets/icons/MdiLightbulbOutline.svg) no-repeat 100% 100%;
    mask: url(/assets/icons/MdiLightbulbOutline.svg) no-repeat 100% 100%;
    -webkit-mask-size: cover;
    mask-size: cover;
}

.MdiLightbulbOutline,
.breathing-glow {
    background: linear-gradient(
        90deg,
        rgba(230, 230, 230, 0.7) 0%,
        rgba(255, 255, 255, 1) 50%,
        rgba(230, 230, 230, 0.7) 100%
    );
    background-size: 200% auto;
    animation: breathing-glow-animation 3s linear infinite;

    color: transparent;
}

.breathing-glow {
    -webkit-background-clip: text;
    background-clip: text;
}

html:not(.dark) .breathing-glow {
    background: linear-gradient(
        90deg,
        rgba(80, 80, 80, 0.7) 0%,
        rgba(0, 0, 0, 1) 50%,
        rgba(80, 80, 80, 0.7) 100%
    );
    background-size: 200% auto;
}

@keyframes breathing-glow-animation {
    from {
        background-position: 200% center;
    }
    to {
        background-position: -200% center;
    }
}
</style>
