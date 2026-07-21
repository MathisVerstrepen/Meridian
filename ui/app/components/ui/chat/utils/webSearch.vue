<script lang="ts" setup>
import type { WebSearch } from '@/types/webSearch';

const props = defineProps<{
    webSearches: WebSearch[];
}>();

const emit = defineEmits<{
    'open-details': [toolCallId: string];
}>();

const hasError = computed(() => props.webSearches.some((search) => !!search.error));
const isStreaming = computed(() => props.webSearches.some((search) => !!search.streaming));

const VISIBLE_FAVICON_LIMIT = 3;
const totalPages = computed(() =>
    props.webSearches.reduce((total, search) => total + search.results.length, 0),
);
const faviconSources = computed(() =>
    props.webSearches.flatMap((search) =>
        search.results.flatMap((result) =>
            result.favicon
                ? [
                      {
                          src: result.favicon,
                          label: result.title || result.link,
                      },
                  ]
                : [],
        ),
    ),
);
const visibleFavicons = computed(() => faviconSources.value.slice(0, VISIBLE_FAVICON_LIMIT));
</script>

<template>
    <HeadlessDisclosure v-if="props.webSearches.length" v-slot="{ open: isWebSearchOpen }">
        <HeadlessDisclosureButton
            data-testid="web-search-disclosure-button"
            class="dark:hover:text-soft-silk/60 hover:text-anthracite/20 dark:text-soft-silk/80
                text-obsidian mb-2 flex h-9 max-w-full cursor-pointer items-center gap-2
                overflow-hidden rounded-lg transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': isStreaming,
                'text-red-500!': hasError,
            }"
        >
            <UiIcon name="MdiMagnify" class="h-4 w-4 shrink-0" />
            <span class="text-sm font-bold">
                {{ isStreaming ? 'Searching web...' : 'Web Search' }}
            </span>
            <span
                v-if="totalPages > 0"
                data-testid="web-search-summary-pill"
                class="border-stone-gray/20 flex h-7 shrink-0 items-center gap-2 rounded-full border
                    px-2 text-xs font-semibold"
            >
                <span
                    v-if="visibleFavicons.length"
                    data-testid="web-search-summary-favicon-stack"
                    class="flex -space-x-1.5"
                >
                    <img
                        v-for="(favicon, faviconIndex) in visibleFavicons"
                        :key="`${favicon.src}-${faviconIndex}`"
                        data-testid="web-search-summary-favicon"
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
                :class="isWebSearchOpen ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>

        <HeadlessDisclosurePanel
            data-testid="web-search-disclosure-panel"
            as="div"
            class="mb-2 flex w-full flex-col gap-2"
        >
            <div
                v-for="(search, searchIndex) in props.webSearches"
                :key="`${search.toolCallId || 'search'}-${search.query}-${searchIndex}`"
                data-testid="web-search-row"
                :data-search-index="searchIndex"
                class="flex w-full min-w-0 flex-col"
            >
                <div
                    class="dark:text-soft-silk/80 text-obsidian flex min-h-9 max-w-full
                        items-center gap-2 overflow-hidden rounded-lg"
                    :class="{
                        'animate-pulse': search.streaming,
                        'text-red-500!': search.error,
                    }"
                >
                    <UiIcon name="MdiMagnify" class="h-4 w-4 shrink-0" />
                    <div
                        v-if="!search.streaming"
                        :title="`Web Search for '${search.query}'`"
                        class="flex max-w-full min-w-0 items-center gap-1 overflow-hidden text-sm
                            font-bold"
                    >
                        <span class="shrink-0">
                            {{ search.error ? 'Search Failed' : 'Web Search for' }}
                        </span>
                        <span
                            class="dark:text-soft-silk text-obsidian overflow-hidden text-ellipsis
                                whitespace-nowrap italic"
                        >
                            "{{ search.query }}"
                        </span>
                    </div>
                    <div v-else class="text-sm font-bold">Searching web...</div>
                    <button
                        v-if="search.toolCallId && !search.streaming"
                        type="button"
                        data-testid="web-search-details-button"
                        :aria-label="`View details for web search '${search.query}'`"
                        class="hover:bg-stone-gray/10 mb-0.5 ml-2 flex items-center justify-center
                            rounded-md p-1.5 transition-colors duration-200"
                        @click="emit('open-details', search.toolCallId)"
                    >
                        <UiIcon name="MajesticonsInformationCircleLine" class="h-4 w-4" />
                    </button>
                </div>

                <div
                    v-if="search.error"
                    class="flex w-full min-w-0 grow flex-col overflow-hidden rounded-lg border
                        border-red-500/20 bg-red-500/20 p-2 text-xs text-red-500"
                >
                    {{ search.error }}
                </div>
                <div
                    v-else-if="!search.streaming"
                    class="border-stone-gray/10 flex w-full min-w-0 grow flex-col overflow-hidden
                        rounded-lg border"
                >
                    <div
                        v-for="(result, resultIndex) in search.results"
                        :key="`${result.link}-${resultIndex}`"
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
                                class="mr-2 h-4 w-4 shrink-0"
                            />
                            <span class="min-w-0 truncate">{{ result.title }}</span>
                            <UiIcon name="MdiArrowTopRightThick" class="h-4 w-4 shrink-0" />
                        </a>
                        <p class="text-stone-gray mt-1 mb-0 text-xs">{{ result.content }}</p>
                    </div>
                </div>
            </div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>

<style scoped></style>
