<script setup lang="ts">
import type { ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

const { $markedWorker } = useNuxtApp();

const contentHtml = ref('');
let lastRenderId = 0;

const args = computed(() => {
    const a = props.detail.arguments as Record<string, unknown>;
    return {
        url: String(a?.url || ''),
    };
});

const result = computed(() => {
    const r = props.detail.result as Record<string, unknown>;
    const content =
        typeof r?.markdown_content === 'string'
            ? r.markdown_content
            : typeof r?.content === 'string'
            ? r.content
            : typeof r?.text === 'string'
              ? r.text
              : null;
    return {
        content,
        error: r?.error ? String(r.error) : null,
    };
});

const hostname = computed(() => {
    try {
        return new URL(args.value.url).hostname;
    } catch {
        return args.value.url;
    }
});

const faviconUrl = computed(() => {
    return `https://www.google.com/s2/favicons?domain=${hostname.value}&sz=32`;
});

const contentLineCount = computed(() => {
    if (!result.value.content) return 0;
    return result.value.content.split('\n').length;
});

const renderContent = async () => {
    if (!result.value.content) {
        contentHtml.value = '';
        return;
    }

    const renderId = ++lastRenderId;
    const html = await $markedWorker.parse(result.value.content);
    if (renderId !== lastRenderId) return;
    contentHtml.value = html;
};

watch(
    () => result.value.content,
    () => void renderContent(),
    { immediate: true },
);
</script>

<template>
    <div class="space-y-5">
        <!-- URL -->
        <section v-if="args.url">
            <p class="text-stone-gray/60 mb-1.5 text-[11px] font-medium uppercase tracking-wider">
                Source
            </p>
            <a
                :href="args.url"
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
                        {{ args.url }}
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
        <section v-if="result.content">
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

        <!-- Error -->
        <section v-if="result.error">
            <div
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/[0.06]
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">{{ result.error }}</p>
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
