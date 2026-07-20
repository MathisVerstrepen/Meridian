<script lang="ts" setup>
import type { FetchedPage } from '@/types/webSearch';
import type { FetchedPageDetailSelection } from '@/types/toolCall';

const props = defineProps<{
    fetchedPages: FetchedPage[];
}>();

const emit = defineEmits<{
    'open-details': [toolCallId: string, selection: FetchedPageDetailSelection];
}>();

const hasError = computed(() => props.fetchedPages.some((page) => !!page.error));

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

const VISIBLE_FAVICON_LIMIT = 3;
const totalPages = computed(() => props.fetchedPages.length);
const faviconSources = computed(() =>
    props.fetchedPages.flatMap((page) => {
        const src = faviconFromLink(page.url);
        return src
            ? [
                  {
                      src,
                      label: hostFromLink(page.url),
                  },
              ]
            : [];
    }),
);
const visibleFavicons = computed(() => faviconSources.value.slice(0, VISIBLE_FAVICON_LIMIT));
</script>

<template>
    <HeadlessDisclosure
        v-if="props.fetchedPages.length"
        v-slot="{ open: isFetchedPageOpen }"
        :default-open="hasError"
    >
        <HeadlessDisclosureButton
            data-testid="fetched-page-disclosure-button"
            class="dark:hover:text-soft-silk/60 hover:text-anthracite/20 dark:text-soft-silk/80
                text-obsidian mb-2 flex min-h-9 w-fit cursor-pointer items-center gap-2 rounded-lg
                transition-colors duration-200 ease-in-out"
        >
            <UiIcon name="MdiFileDocumentOutline" class="h-4 w-4 shrink-0" />
            <span class="shrink-0 text-sm font-bold">Read Content from</span>
            <span
                v-if="totalPages > 0"
                data-testid="fetched-page-summary-pill"
                class="border-stone-gray/20 flex h-7 shrink-0 items-center gap-2 rounded-full border
                    px-2 text-xs font-semibold"
            >
                <span
                    v-if="visibleFavicons.length"
                    data-testid="fetched-page-summary-favicon-stack"
                    class="flex -space-x-1.5"
                >
                    <img
                        v-for="(favicon, faviconIndex) in visibleFavicons"
                        :key="`${favicon.src}-${faviconIndex}`"
                        data-testid="fetched-page-summary-favicon"
                        :src="favicon.src"
                        :alt="`${favicon.label} favicon`"
                        :title="favicon.label"
                        class="bg-soft-silk ring-soft-silk dark:bg-anthracite dark:ring-anthracite
                            h-4 w-4 rounded-full ring-1"
                    />
                </span>
                <span>{{ totalPages }} {{ totalPages === 1 ? 'web page' : 'web pages' }}</span>
            </span>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="h-4 w-4 transition-transform duration-200"
                :class="isFetchedPageOpen ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>

        <HeadlessDisclosurePanel
            data-testid="fetched-page-disclosure-panel"
            as="div"
            class="mb-2 flex flex-wrap items-center gap-2 overflow-hidden"
        >
            <div
                v-for="(fetchedPage, fetchedPageIndex) in props.fetchedPages"
                :key="`${fetchedPage.toolCallId || fetchedPage.url}-${fetchedPage.url}-${fetchedPageIndex}`"
                data-testid="fetched-page-row"
                :data-fetched-page-index="fetchedPageIndex"
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
                    type="button"
                    data-testid="fetched-page-details-button"
                    :aria-label="`View details for fetched page '${fetchedPage.url}'`"
                    class="hover:bg-stone-gray/10 ml-0.5 rounded-md p-1 transition-colors
                        duration-200"
                    @click="
                        emit('open-details', fetchedPage.toolCallId, {
                            kind: 'fetched-page',
                            index: fetchedPageIndex,
                            url: fetchedPage.url,
                        })
                    "
                >
                    <UiIcon
                        name="MajesticonsInformationCircleLine"
                        class="text-soft-silk/80 h-4 w-4"
                    />
                </button>
            </div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>
