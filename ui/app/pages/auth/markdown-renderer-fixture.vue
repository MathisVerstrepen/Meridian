<script setup lang="ts">
import type { Message } from '@/types/graph';
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
    parsedSegmentCount?: number;
    reusedSegmentCount?: number;
    enhancedSegmentCount?: number;
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
const stablePrefixRetained = ref<boolean | null>(null);
let capturedPrefixRoot: Element | null = null;
const NARROW_WATCH_FIXTURE_CASE_KEY = 'externalLinkFaviconsMainThread';
const REPLACEMENT_NODE_ID = 'fixture-node-external-link-favicons-replacement';

const message = ref<Message>({
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

const applySameLengthRevision = () => {
    const textContent = message.value.content.find(
        (content) => content.type === MessageContentTypeEnum.TEXT,
    );
    if (!textContent?.text) return;

    textContent.text = textContent.text.replace('External', 'Revision');
};

const replaceActiveMessage = () => {
    message.value = {
        ...message.value,
        content: message.value.content.map((content) => ({ ...content })),
        node_id: REPLACEMENT_NODE_ID,
    };
};

const syncPerfSummary = () => {
    if (!import.meta.client || !import.meta.dev) {
        return;
    }

    const perfWindow = window as typeof window & {
        __markdownRendererPerf?: {
            lastRun?: {
                status?: string;
                measures?: Record<string, number>;
                parsedSegmentCount?: number;
                reusedSegmentCount?: number;
                enhancedSegmentCount?: number;
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
        parsedSegmentCount: lastRun.parsedSegmentCount,
        reusedSegmentCount: lastRun.reusedSegmentCount,
        enhancedSegmentCount: lastRun.enhancedSegmentCount,
    };
};

const handleRendered = () => {
    isRendered.value = true;
    syncPerfSummary();
    if (streamingDone.value && capturedPrefixRoot) {
        const renderKey = (capturedPrefixRoot as HTMLElement).dataset.markdownSegmentKey;
        const currentRoot = renderKey
            ? document.querySelector(`[data-markdown-segment-key="${renderKey}"]`)
            : null;
        stablePrefixRetained.value = capturedPrefixRoot.isSameNode(currentRoot);
    }
};

if (isStreamingMode) {
    onMounted(() => {
        const fullText = fixtureCase.rawMessage;
        let cursor = 0;

        const deliver = () => {
            if (cursor >= fullText.length) {
                const perfStore = (
                    window as typeof window & {
                        __markdownRendererPerf?: {
                            lastRun?: {
                                markdownLength?: number;
                                isStreaming?: boolean;
                                status?: string;
                            };
                        };
                    }
                ).__markdownRendererPerf;
                const lastRun = perfStore?.lastRun;
                if (
                    lastRun?.markdownLength !== fullText.trim().length ||
                    lastRun.isStreaming !== true ||
                    lastRun.status !== 'completed'
                ) {
                    requestAnimationFrame(deliver);
                    return;
                }
                // All chunks delivered, mark streaming as done.
                // This flips isCurrentlyStreaming to false, causing one final
                // non-streaming parse that emits 'rendered'.
                streamingDone.value = true;
                return;
            }
            cursor = Math.min(cursor + STREAM_CHUNK_SIZE, fullText.length);
            message.value.content[0]!.text = fullText.slice(0, cursor);
            nextTick(() => {
                if (capturedPrefixRoot) return;
                const roots = document.querySelectorAll(
                    '[data-testid="markdown-renderer-response"] [data-markdown-segment-key]',
                );
                if (roots.length > 1) capturedPrefixRoot = roots[0] ?? null;
            });
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
        :data-stable-prefix-retained="
            stablePrefixRetained === null ? '' : stablePrefixRetained ? 'true' : 'false'
        "
        :data-parsed-segment-count="perfSummary?.parsedSegmentCount ?? ''"
        :data-reused-segment-count="perfSummary?.reusedSegmentCount ?? ''"
        :data-enhanced-segment-count="perfSummary?.enhancedSegmentCount ?? ''"
        class="bg-obsidian min-h-screen p-8"
    >
        <div id="fullscreen-mountpoint" data-testid="fullscreen-mountpoint" />
        <div class="mx-auto flex max-w-5xl flex-col gap-6">
            <div class="text-soft-silk/70 text-sm font-semibold tracking-[0.24em] uppercase">
                Markdown renderer fixture
            </div>

            <div v-if="fixtureCase.key === NARROW_WATCH_FIXTURE_CASE_KEY" class="flex gap-3">
                <button
                    type="button"
                    data-testid="apply-same-length-revision"
                    @click="applySameLengthRevision"
                >
                    Apply same-length revision
                </button>
                <button
                    type="button"
                    data-testid="replace-active-message"
                    @click="replaceActiveMessage"
                >
                    Replace active message
                </button>
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
