<script setup lang="ts">
import type { FetchedPageDetailSelection, ToolCallDetail } from '@/types/toolCall';

const props = withDefaults(
    defineProps<{
        detail: ToolCallDetail;
        fetchedPageSelection?: FetchedPageDetailSelection | null;
    }>(),
    {
        fetchedPageSelection: null,
    },
);

const { $markedWorker } = useNuxtApp();

const contentHtml = ref('');
let lastRenderId = 0;

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return !!value && typeof value === 'object' && !Array.isArray(value);
};

const asNonEmptyString = (value: unknown): string | null => {
    if (typeof value !== 'string' || !value.trim()) return null;
    return value;
};

const normalized = computed(() => {
    const args = isRecord(props.detail.arguments) ? props.detail.arguments : {};
    const result = isRecord(props.detail.result) ? props.detail.result : {};
    const isCanonical =
        Object.prototype.hasOwnProperty.call(result, 'pages') || Array.isArray(args.urls);
    const rootError = asNonEmptyString(result.error);

    if (!isCanonical) {
        const content =
            asNonEmptyString(result.markdown_content) ||
            asNonEmptyString(result.content) ||
            asNonEmptyString(result.text);
        return {
            url: asNonEmptyString(args.url) || '',
            content,
            localError: null,
            rootError,
        };
    }

    const selection: unknown = props.fetchedPageSelection;
    if (
        !isRecord(selection) ||
        selection.kind !== 'fetched-page' ||
        !Number.isInteger(selection.index) ||
        (selection.index as number) < 0 ||
        !Array.isArray(result.pages) ||
        (selection.index as number) >= result.pages.length
    ) {
        return {
            url: '',
            content: null,
            localError: null,
            rootError,
        };
    }

    const index = selection.index as number;
    const page = result.pages[index];
    if (!isRecord(page)) {
        return {
            url: '',
            content: null,
            localError: null,
            rootError,
        };
    }

    const argumentUrl = Array.isArray(args.urls) ? asNonEmptyString(args.urls[index]) : null;
    return {
        url:
            asNonEmptyString(page.url) ||
            argumentUrl ||
            asNonEmptyString(selection.url) ||
            '',
        content: asNonEmptyString(page.markdown_content),
        localError: asNonEmptyString(page.error),
        rootError,
    };
});

const hostname = computed(() => {
    try {
        return new URL(normalized.value.url).hostname;
    } catch {
        return normalized.value.url;
    }
});

const faviconUrl = computed(() => {
    return `https://www.google.com/s2/favicons?domain=${hostname.value}&sz=32`;
});

const contentLineCount = computed(() => {
    if (!normalized.value.content) return 0;
    return normalized.value.content.split('\n').length;
});

const renderContent = async () => {
    const renderId = ++lastRenderId;
    contentHtml.value = '';
    if (!normalized.value.content) return;

    const html = await $markedWorker.parse(normalized.value.content);
    if (renderId !== lastRenderId) return;
    contentHtml.value = html;
};

watch(
    () => normalized.value.content,
    () => void renderContent(),
    { immediate: true },
);
</script>

<template>
    <div class="space-y-5">
        <!-- URL -->
        <section v-if="normalized.url" data-testid="link-extraction-source">
            <p class="text-stone-gray/60 mb-1.5 text-[11px] font-medium uppercase tracking-wider">
                Source
            </p>
            <a
                :href="normalized.url"
                target="_blank"
                rel="noopener noreferrer"
                class="le-source group inline-flex items-center gap-2.5 rounded-lg p-2.5
                    transition-colors duration-150"
            >
                <img
                    :src="faviconUrl"
                    :alt="hostname"
                    class="h-4 w-4 shrink-0 rounded-sm"
                    loading="lazy"
                />
                <div class="min-w-0">
                    <p class="text-soft-silk text-[13px] font-medium group-hover:underline">
                        {{ hostname }}
                    </p>
                    <p class="text-stone-gray/40 mt-0.5 truncate text-[11px]">
                        {{ normalized.url }}
                    </p>
                </div>
                <UiIcon
                    name="MaterialSymbolsOpenInNewRounded"
                    class="text-stone-gray/40 h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity
                        duration-150 group-hover:opacity-100"
                />
            </a>
        </section>

        <!-- Extracted Content -->
        <section v-if="normalized.content" data-testid="link-extraction-content">
            <div class="mb-1.5 flex items-center justify-between">
                <p
                    class="text-stone-gray/60 text-[11px] font-medium uppercase tracking-wider"
                >
                    Extracted content
                </p>
                <span class="text-stone-gray/40 text-[11px]">
                    {{ contentLineCount }} lines
                </span>
            </div>
            <div
                class="le-markdown-content prose prose-invert custom_scroll max-w-none
                    max-h-[400px] overflow-y-auto rounded-lg bg-black/20 p-3.5
                    text-soft-silk/70"
                v-html="contentHtml"
            />
        </section>

        <!-- Selected page error -->
        <section v-if="normalized.localError" data-testid="link-extraction-local-error">
            <div
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/6
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">
                    {{ normalized.localError }}
                </p>
            </div>
        </section>

        <!-- Root error -->
        <section v-if="normalized.rootError" data-testid="link-extraction-root-error">
            <div
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/6
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">
                    {{ normalized.rootError }}
                </p>
            </div>
        </section>
    </div>
</template>

<style scoped>
.le-source {
    background: rgba(255, 255, 255, 0.02);
}

.le-source:hover {
    background: rgba(255, 255, 255, 0.04);
}

.le-markdown-content:deep(:first-child) {
    margin-top: 0;
}

.le-markdown-content:deep(:last-child) {
    margin-bottom: 0;
}

.le-markdown-content:deep(pre) {
    max-width: 100%;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.le-markdown-content:deep(pre code) {
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}
</style>
