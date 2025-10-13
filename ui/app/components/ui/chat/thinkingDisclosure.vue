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
            class="dark:hover:text-soft-silk/50 hover:text-anthracite/20 dark:text-soft-silk/80
                text-obsidian flex h-fit w-fit cursor-pointer items-center gap-2 rounded-lg py-2
                transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': isStreaming,
            }"
            @click="handleToggle(isThinkingOpen)"
        >
            <UiIcon name="MdiLightbulbOutline" class="h-4 w-4" />
            <span class="text-sm font-bold">{{ isStreaming ? 'Thinking...' : 'Thoughts' }}</span>
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

<style scoped></style>
