<script setup lang="ts">
import type { ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

interface SearchResult {
    title: string;
    url: string;
    content: string;
}

interface NormalizedSearch {
    query: string;
    results: SearchResult[];
    error: string | null;
}

const isRecord = (value: RuntimeValue): value is Record<string, JsonValue> => {
    return !!value && typeof value === 'object' && !Array.isArray(value);
};

const asNonEmptyString = (value: RuntimeValue): string | null => {
    if (!isRuntimeString(value) || !value.trim()) return null;
    return value;
};

const normalizeResults = (value: RuntimeValue): SearchResult[] => {
    if (!Array.isArray(value)) return [];
    return value
        .filter(isRecord)
        .map((item) => ({
            title: String(item.title || ''),
            url: String(item.url || ''),
            content: String(item.content || ''),
        }))
        .filter((item) => item.url);
};

const args = computed(() => {
    const value = isRecord(props.detail.arguments) ? props.detail.arguments : {};
    return {
        value,
        queries: Array.isArray(value.queries) ? value.queries : [],
        timeRange: value.time_range ? String(value.time_range) : null,
        language: value.language ? String(value.language) : null,
    };
});

const rootError = computed(() => {
    const result = props.detail.result;
    if (!isRecord(result) || !Array.isArray(result.searches)) return null;
    return asNonEmptyString(result.error);
});

const searches = computed<NormalizedSearch[]>(() => {
    const result = props.detail.result;

    if (isRecord(result) && Array.isArray(result.searches)) {
        return result.searches.flatMap((entry, index) => {
            if (!isRecord(entry)) return [];

            return [
                {
                    query:
                        asNonEmptyString(entry.query) ||
                        asNonEmptyString(args.value.queries[index]) ||
                        '',
                    results: normalizeResults(entry.results),
                    error: asNonEmptyString(entry.error),
                },
            ];
        });
    }

    if (Array.isArray(result) && Object.prototype.hasOwnProperty.call(args.value.value, 'query')) {
        return [
            {
                query: asNonEmptyString(args.value.value.query) || '',
                results: normalizeResults(result),
                error: null,
            },
        ];
    }

    return [];
});

const getHostname = (url: string): string => {
    try {
        return new URL(url).hostname;
    } catch {
        return url;
    }
};

const getFaviconUrl = (url: string): string => {
    const hostname = getHostname(url);
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=32`;
};
</script>

<template>
    <div class="space-y-5">
        <!-- Shared search metadata -->
        <section
            v-if="args.timeRange || args.language"
            class="flex items-center justify-end gap-1.5 text-[11px]"
        >
            <span
                v-if="args.timeRange"
                data-testid="web-search-time-range"
                class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
            >
                {{ args.timeRange }}
            </span>
            <span
                v-if="args.language"
                data-testid="web-search-language"
                class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
            >
                {{ args.language }}
            </span>
        </section>

        <!-- Root error -->
        <section v-if="rootError" data-testid="web-search-root-error">
            <div
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/6
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">{{ rootError }}</p>
            </div>
        </section>

        <!-- Searches -->
        <section
            v-for="(search, searchIndex) in searches"
            :key="`${searchIndex}-${search.query}`"
            data-testid="web-search-entry"
            :data-search-index="searchIndex"
            class="space-y-3"
        >
            <div>
                <p
                    class="text-stone-gray/60 mb-1 text-[11px] font-medium uppercase tracking-wider"
                >
                    Query
                </p>
                <p
                    data-testid="web-search-query"
                    class="text-soft-silk/90 text-[13px] font-medium"
                >
                    "{{ search.query }}"
                </p>
            </div>

            <div
                v-if="search.error"
                data-testid="web-search-entry-error"
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/6
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">{{ search.error }}</p>
            </div>

            <template v-else-if="search.results.length">
                <p
                    data-testid="web-search-result-count"
                    class="text-stone-gray/60 text-[11px] font-medium uppercase tracking-wider"
                >
                    {{ search.results.length }} result{{ search.results.length === 1 ? '' : 's' }}
                </p>
                <div class="space-y-1.5">
                    <a
                        v-for="(item, resultIndex) in search.results"
                        :key="`${searchIndex}-${resultIndex}-${item.url}`"
                        :href="item.url"
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid="web-search-result"
                        class="ws-result group block rounded-lg p-3 transition-colors duration-150"
                    >
                        <div class="flex items-start gap-2.5">
                            <img
                                :src="getFaviconUrl(item.url)"
                                :alt="getHostname(item.url)"
                                class="mt-0.5 h-4 w-4 shrink-0 rounded-sm"
                                loading="lazy"
                            />
                            <div class="min-w-0 flex-1">
                                <p
                                    class="text-soft-silk truncate text-[13px] font-medium
                                        group-hover:underline"
                                >
                                    {{ item.title || getHostname(item.url) }}
                                </p>
                                <p class="text-stone-gray/50 mt-0.5 truncate text-[11px]">
                                    {{ getHostname(item.url) }}
                                </p>
                                <p
                                    v-if="item.content"
                                    class="text-soft-silk/45 mt-1.5 line-clamp-2 text-[12px]
                                        leading-relaxed"
                                >
                                    {{ item.content }}
                                </p>
                            </div>
                            <UiIcon
                                name="MaterialSymbolsOpenInNewRounded"
                                class="text-stone-gray/40 mt-0.5 h-3.5 w-3.5 shrink-0 opacity-0
                                    transition-opacity duration-150 group-hover:opacity-100"
                            />
                        </div>
                    </a>
                </div>
            </template>

            <div
                v-else
                data-testid="web-search-entry-empty"
                class="flex items-center justify-center py-8"
            >
                <p class="text-stone-gray/50 text-sm">No results returned.</p>
            </div>
        </section>
    </div>
</template>

<style scoped>
.ws-result {
    background: rgba(255, 255, 255, 0.02);
}

.ws-result:hover {
    background: rgba(255, 255, 255, 0.04);
}
</style>
