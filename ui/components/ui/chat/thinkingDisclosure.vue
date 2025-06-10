<script lang="ts" setup>
defineProps<{
    thinkingHtml: string;
    isStreaming?: boolean;
}>();
</script>

<template>
    <HeadlessDisclosure v-slot="{ open }">
        <HeadlessDisclosureButton
            class="bg-anthracite hover:bg-anthracite/75 mb-2 flex h-fit w-fit cursor-pointer items-center gap-2
                rounded-lg px-4 py-2 transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': isStreaming,
            }"
        >
            <UiIcon name="RiBrain2Line" class="text-soft-silk/80 h-4 w-4" />
            <span class="text-soft-silk/80 text-sm font-bold">Thoughts</span>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="text-soft-silk/80 h-4 w-4 transition-transform duration-200"
                :class="open ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>
        <HeadlessDisclosurePanel
            as="div"
            class="col-span-2 col-start-1 row-start-2 flex h-full w-full items-stretch gap-4"
        >
            <div class="bg-anthracite w-1 shrink-0 rounded"></div>
            <div
                class="prose prose-invert h-full w-full max-w-none pr-5 opacity-75"
                v-html="thinkingHtml"
            ></div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>

<style scoped></style>
