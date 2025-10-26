<script lang="ts" setup>
import type { FetchedPage } from '@/types/webSearch';

const props = defineProps<{
    fetchedPages: FetchedPage[];
}>();

const faviconFromLink = (link: string): string => {
    try {
        const url = new URL(link);
        return `https://www.google.com/s2/favicons?domain=${url.hostname}&sz=32`;
    } catch {
        return '';
    }
};

const hostFromLink = (link: string): string => {
    try {
        const url = new URL(link);
        return url.hostname;
    } catch {
        return link;
    }
};
</script>

<template>
    <div
        class="dark:text-soft-silk/80 text-obsidian mb-2 flex min-h-9 w-fit items-center gap-2
            rounded-lg"
    >
        <UiIcon name="MdiFileDocumentOutline" class="h-4 w-4 shrink-0" />
        <span
            class="flex flex-wrap items-center gap-2 self-center overflow-hidden text-sm font-bold"
        >
            <span class="shrink-0">Read Content from</span>

            <NuxtLink
                v-for="fetchedPage in props.fetchedPages"
                :key="fetchedPage.url"
                :to="fetchedPage.url"
                target="_blank"
                rel="noopener noreferrer"
                class="dark:border-anthracite border-stone-gray dark:text-soft-silk text-obsidian
                    flex rounded-lg border py-1 pr-2 pl-1 text-xs"
                :class="{
                    '!border-red-500/20 bg-red-500/20 !text-red-500':
                        fetchedPage.error && fetchedPage.error.length > 0,
                }"
            >
                <img
                    :src="faviconFromLink(fetchedPage.url)"
                    alt="Favicon"
                    class="mr-2 h-4 w-4 flex-shrink-0 rounded"
                />
                <span class="overflow-hidden text-ellipsis whitespace-nowrap italic">
                    {{ hostFromLink(fetchedPage.url) }} {{ fetchedPage.error ? ' (Error)' : '' }}
                </span>
            </NuxtLink>
        </span>
    </div>
</template>
