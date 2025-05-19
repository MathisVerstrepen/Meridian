<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

defineProps<{
    thinkingHtml: string;
    nodeType: NodeTypeEnum
}>();
</script>

<template>
    <HeadlessDisclosure as="div" class="mt-2 mb-4 max-w-none" v-slot="{ open }" v-if="thinkingHtml">
        <HeadlessDisclosureButton
            class="bg-anthracite hover:bg-anthracite/75 mb-2 flex cursor-pointer items-center gap-2 rounded-lg px-4
                py-2 transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': nodeType === NodeTypeEnum.STREAMING,
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
        <HeadlessDisclosurePanel as="div" class="flex h-full w-full items-stretch gap-4">
            <div class="bg-anthracite w-1 shrink-0 rounded"></div>
            <div
                class="prose prose-invert h-full w-full max-w-none pr-5 opacity-75"
                v-html="thinkingHtml"
            ></div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>

<style scoped></style>
