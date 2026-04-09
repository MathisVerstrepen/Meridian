<script lang="ts" setup>
import type { FetchedPage } from '@/types/webSearch';

const props = defineProps<{
    fetchedPages: FetchedPage[];
}>();

const emit = defineEmits(['open-details']);

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

            <div
                v-for="fetchedPage in props.fetchedPages"
                :key="`${fetchedPage.toolCallId || fetchedPage.url}-${fetchedPage.url}`"
                class="dark:border-anthracite border-stone-gray dark:text-soft-silk text-obsidian
                    flex items-center gap-1 rounded-lg border p-0.5 text-xs"
                :class="{
                    'border-red-500/20! bg-red-500/20 text-red-500!':
                        fetchedPage.error && fetchedPage.error.length > 0,
                }"
            >
                <NuxtLink
                    :to="fetchedPage.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="flex items-center overflow-hidden"
                >
                    <img
                        :src="faviconFromLink(fetchedPage.url)"
                        alt="Favicon"
                        class="mr-2 ml-1 h-4 w-4 shrink-0 rounded"
                    />
                    <span class="overflow-hidden text-ellipsis whitespace-nowrap italic">
                        {{ hostFromLink(fetchedPage.url) }}
                        {{ fetchedPage.error ? ' (Error)' : '' }}
                    </span>
                </NuxtLink>
                <button
                    v-if="fetchedPage.toolCallId"
                    class="hover:bg-stone-gray/10 ml-0.5 rounded-md p-1 transition-colors
                        duration-200"
                    @click="emit('open-details', fetchedPage.toolCallId)"
                >
                    <UiIcon
                        name="MajesticonsInformationCircleLine"
                        class="text-soft-silk/80 h-4 w-4"
                    />
                </button>
            </div>
        </span>
    </div>
</template>
