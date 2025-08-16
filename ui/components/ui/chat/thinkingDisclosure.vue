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
    <HeadlessDisclosure v-slot="{ open }" :defaultOpen="generalSettings.alwaysThinkingDisclosures">
        <HeadlessDisclosureButton
            @click="handleToggle(open)"
            class="dark:bg-anthracite bg-anthracite/20 dark:hover:bg-anthracite/75 hover:bg-anthracite/40
                dark:text-soft-silk/80 text-obsidian mb-2 flex h-fit w-fit cursor-pointer items-center gap-2
                rounded-lg px-4 py-2 transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': isStreaming,
            }"
        >
            <UiIcon name="RiBrain2Line" class="h-4 w-4" />
            <span class="text-sm font-bold">Thoughts</span>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="h-4 w-4 transition-transform duration-200"
                :class="open ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>
        <HeadlessDisclosurePanel
            as="div"
            class="col-span-2 col-start-1 row-start-2 flex h-full w-full items-stretch gap-4"
        >
            <div class="dark:bg-anthracite bg-anthracite/20 w-1 shrink-0 rounded"></div>
            <div
                class="prose prose-invert h-full w-full max-w-none pr-5 opacity-75"
                v-html="thinkingHtml"
                :class="{
                    'hide-code-scrollbar': isStreaming,
                }"
            ></div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>

<style scoped></style>
