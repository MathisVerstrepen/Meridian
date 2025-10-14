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
                text-obsidian mb-2 flex h-9 max-w-full cursor-pointer items-center gap-2
                overflow-hidden rounded-lg transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': props.webSearch.streaming,
            }"
        >
            <UiIcon name="MdiMagnify" class="h-4 w-4 shrink-0" />
            <div
                v-if="!props.webSearch.streaming"
                :title="`Web Search for '${props.webSearch.query}'`"
                class="flex max-w-full min-w-0 items-center gap-1 overflow-hidden text-sm font-bold"
            >
                <span class="shrink-0">Web Search for</span>
                <span
                    class="dark:text-soft-silk text-obsidian overflow-hidden text-ellipsis
                        whitespace-nowrap italic"
                    >"{{ props.webSearch.query }}"</span
                >
            </div>
            <div v-else class="text-sm font-bold">Searching web...</div>
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
                class="border-stone-gray/10 flex w-full min-w-0 grow flex-col overflow-hidden
                    rounded-lg border"
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
                        class="text-soft-silk flex h-6 w-full min-w-0 items-center text-sm
                            font-semibold"
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
