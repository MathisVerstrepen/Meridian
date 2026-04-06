<script setup lang="ts">
import type { ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

const args = computed(() => {
    const a = props.detail.arguments as Record<string, unknown>;
    return {
        query: String(a?.query || ''),
        time_range: a?.time_range ? String(a.time_range) : null,
        language: a?.language ? String(a.language) : null,
    };
});

interface SearchResult {
    title: string;
    url: string;
    content: string;
}

const results = computed<SearchResult[]>(() => {
    const r = props.detail.result;
    if (!Array.isArray(r)) return [];
    return r
        .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
        .map((item) => ({
            title: String(item.title || ''),
            url: String(item.url || ''),
            content: String(item.content || ''),
        }))
        .filter((item) => item.url);
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
        <!-- Query -->
        <section class="flex flex-wrap items-start justify-between gap-3">
            <div>
                <p
                    class="text-stone-gray/60 mb-1 text-[11px] font-medium uppercase tracking-wider"
                >
                    Query
                </p>
                <p class="text-soft-silk/90 text-[13px] font-medium">
                    "{{ args.query }}"
                </p>
            </div>
            <div
                v-if="args.time_range || args.language"
                class="flex items-center gap-1.5 text-[11px]"
            >
                <span
                    v-if="args.time_range"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    {{ args.time_range }}
                </span>
                <span
                    v-if="args.language"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    {{ args.language }}
                </span>
            </div>
        </section>

        <!-- Results -->
        <section v-if="results.length">
            <p class="text-stone-gray/60 mb-2.5 text-[11px] font-medium uppercase tracking-wider">
                {{ results.length }} result{{ results.length === 1 ? '' : 's' }}
            </p>
            <div class="space-y-1.5">
                <a
                    v-for="(item, index) in results"
                    :key="index"
                    :href="item.url"
                    target="_blank"
                    rel="noopener noreferrer"
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
        </section>

        <section v-else>
            <div class="flex items-center justify-center py-8">
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
