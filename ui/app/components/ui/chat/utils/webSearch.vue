<script lang="ts" setup>
import type { WebSearch } from '@/types/webSearch';

const props = defineProps<{
    webSearch: WebSearch;
}>();
</script>

<template>
    <HeadlessDisclosure v-slot="{ open: isWebSearchOpen }">
        <HeadlessDisclosureButton
            class="dark:hover:text-soft-silk/60 hover:text-anthracite/20 dark:text-soft-silk/80
                text-obsidian flex h-fit w-fit cursor-pointer items-center gap-2 rounded-lg py-2
                transition-colors duration-200 ease-in-out mb-2"
            :class="{
                'animate-pulse': props.webSearch.streaming,
            }"
        >
            <UiIcon name="MdiMagnify" class="h-4 w-4" />
            <span v-if="!props.webSearch.streaming" class="text-sm font-bold"
                >Web Search for
                <span class="dark:text-soft-silk text-obsidian italic"
                    >"{{ props.webSearch.query }}"</span
                ></span
            >
            <span v-else class="text-sm font-bold">Searching web...</span>
            <UiIcon
                v-if="!props.webSearch.streaming"
                name="LineMdChevronSmallUp"
                class="h-4 w-4 transition-transform duration-200"
                :class="isWebSearchOpen ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>
        <HeadlessDisclosurePanel
            v-if="!props.webSearch.streaming"
            as="div"
            class="mb-2 flex w-full flex-col"
        >
            <div
                class="border-stone-gray/10 flex w-full min-w-0 grow flex-col overflow-hidden rounded-lg border"
            >
                <div
                    v-for="(result, index) in props.webSearch.results"
                    :key="index"
                    class="w-full rounded-lg px-4 py-2 transition-colors duration-200"
                >
                    <a
                        :href="result.link"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-soft-silk flex h-6 w-full min-w-0 items-center text-sm font-semibold"
                    >
                        <img
                            v-if="result.favicon"
                            :src="result.favicon"
                            alt="Favicon"
                            class="mr-2 h-4 w-4 flex-shrink-0"
                        />
                        <span class="min-w-0 truncate">{{ result.title }}</span>
                        <UiIcon name="MdiArrowTopRightThick" class="h-4 w-4 flex-shrink-0" />
                    </a>
                    <p class="text-stone-gray mt-1 mb-0 text-xs">{{ result.content }}</p>
                </div>
            </div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>

<style scoped></style>