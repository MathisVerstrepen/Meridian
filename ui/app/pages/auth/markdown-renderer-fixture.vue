<script setup lang="ts">
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import MarkdownRenderer from '@/components/ui/chat/markdownRenderer.vue';
import NodeTypeIndicator from '@/components/ui/chat/nodeTypeIndicator.vue';
import {
    DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY,
    MARKDOWN_RENDERER_FIXTURE_CASES,
} from '~~/e2e/fixtures/markdownRendererGoldenCase';

definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const isRendered = ref(false);
const perfSummary = ref<{
    status: string;
    measures: Record<string, number>;
} | null>(null);
const route = useRoute();
const caseKey =
    typeof route.query.case === 'string'
        ? route.query.case
        : DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY;
const fixtureCase = MARKDOWN_RENDERER_FIXTURE_CASES[caseKey];

if (!fixtureCase) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Unknown markdown renderer fixture case',
    });
}

// --- Streaming simulation ---
const isStreamingMode = route.query.streaming === 'true';
const STREAM_CHUNK_SIZE = 15;
const streamingDone = ref(false);

const message = reactive({
    role: MessageRoleEnum.assistant,
    content: [
        {
            type: MessageContentTypeEnum.TEXT,
            text: isStreamingMode ? '' : fixtureCase.rawMessage,
        },
    ],
    model: 'fixture-model',
    node_id: fixtureCase.nodeId,
    type: NodeTypeEnum.TEXT_TO_TEXT,
    data: {
        reply: '',
    },
    usageData: null,
});

const isCurrentlyStreaming = computed(() => isStreamingMode && !streamingDone.value);

const syncPerfSummary = () => {
    if (!import.meta.client || !import.meta.dev) {
        return;
    }

    const perfWindow = window as typeof window & {
        __markdownRendererPerf?: {
            lastRun?: {
                status?: string;
                measures?: Record<string, number>;
            };
        };
    };
    const lastRun = perfWindow.__markdownRendererPerf?.lastRun;

    if (!lastRun) {
        perfSummary.value = null;
        return;
    }

    perfSummary.value = {
        status: lastRun.status ?? 'unknown',
        measures: lastRun.measures ?? {},
    };
};

const handleRendered = () => {
    isRendered.value = true;
    syncPerfSummary();
};

if (isStreamingMode) {
    onMounted(() => {
        const fullText = fixtureCase.rawMessage;
        let cursor = 0;

        const deliver = () => {
            if (cursor >= fullText.length) {
                // All chunks delivered, mark streaming as done.
                // This flips isCurrentlyStreaming to false, causing one final
                // non-streaming parse that emits 'rendered'.
                streamingDone.value = true;
                return;
            }
            cursor = Math.min(cursor + STREAM_CHUNK_SIZE, fullText.length);
            message.content[0].text = fullText.slice(0, cursor);
            requestAnimationFrame(deliver);
        };
        requestAnimationFrame(deliver);
    });
}
</script>

<template>
    <div
        data-testid="markdown-renderer-fixture-page"
        :data-rendered="isRendered ? 'true' : 'false'"
        :data-case-key="fixtureCase.key"
        :data-total-ms="perfSummary?.measures.totalMs ?? ''"
        :data-streaming-mode="isStreamingMode ? 'true' : 'false'"
        :data-streaming-done="streamingDone ? 'true' : 'false'"
        class="bg-obsidian min-h-screen p-8"
    >
        <div class="mx-auto flex max-w-5xl flex-col gap-6">
            <div class="text-soft-silk/70 text-sm font-semibold tracking-[0.24em] uppercase">
                Markdown renderer fixture
            </div>

            <div
                v-if="perfSummary"
                data-testid="markdown-renderer-perf-summary"
                class="text-soft-silk/80 rounded-xl border border-white/8 bg-white/4 px-4 py-3
                    text-xs"
            >
                <div class="font-semibold tracking-[0.18em] uppercase">Renderer Perf</div>
                <pre class="mt-2 overflow-x-auto whitespace-pre-wrap">{{
                    JSON.stringify(perfSummary, null, 2)
                }}</pre>
            </div>

            <div
                class="dark:bg-obsidian bg-soft-silk/75 relative ml-[10%] rounded-xl px-6 py-3
                    backdrop-blur-2xl"
            >
                <NodeTypeIndicator :node-type="message.type" />

                <MarkdownRenderer
                    :message="message"
                    :edit-mode="false"
                    :is-streaming="isCurrentlyStreaming"
                    @rendered="handleRendered"
                    @trigger-scroll="undefined"
                    @visualizer-prompt="undefined"
                />
            </div>
        </div>
    </div>
</template>
