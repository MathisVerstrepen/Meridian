<script setup lang="ts">
import { defineAsyncComponent } from 'vue';
import type { RenderedMarkdownSegment } from '@/composables/useMarkdownProcessor';
import type { MarkdownResponseRenderToken } from '@/types/markdownRenderToken';
import GeneratedImageCard from '@/components/ui/chat/utils/generatedImageCard.vue';
import SandboxArtifactDownload from '@/components/ui/chat/utils/sandboxArtifactDownload.vue';
import SandboxHtmlArtifactCard from '@/components/ui/chat/utils/sandboxHtmlArtifactCard.vue';
import ToolQuestionCard from '@/components/ui/chat/utils/toolQuestionCard.vue';
import VisualiseArtifactEmbed from '@/components/ui/chat/utils/visualiseArtifactEmbed.vue';
import CopyButton from '@/components/ui/chat/utils/copyButton.vue';

const FullScreenButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/fullScreenButton.vue'),
);

const props = defineProps<{
    segments: readonly RenderedMarkdownSegment[];
    renderMermaidCharts: (selector?: string) => Promise<void>;
}>();

const emit = defineEmits<{
    openLightbox: [payload: { src: string; prompt: string }];
    visualizerPrompt: [prompt: string];
}>();

const responseRoot = ref<HTMLElement | null>(null);
const renderedMermaidElements = shallowRef<Map<string, HTMLElement>>(new Map());
const HTML_EMBED_CACHE_BUSTER = 'storage-shim-v1';
const CONTROL_CLASS =
    'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm';

const currentTokenKeys = (): Set<string> =>
    new Set(props.segments.flatMap((segment) => segment.tokens.map((token) => token.key)));

const pruneRenderedMermaid = (): void => {
    const tokenKeys = currentTokenKeys();
    const next = new Map(
        [...renderedMermaidElements.value].filter(([key]) => tokenKeys.has(key)),
    );
    if (next.size !== renderedMermaidElements.value.size) {
        renderedMermaidElements.value = next;
    }
};

const getSegmentRoot = (renderKey: string): HTMLElement | null => {
    return (
        Array.from(
            responseRoot.value?.querySelectorAll<HTMLElement>('[data-markdown-segment-key]') ?? [],
        ).find((root) => root.dataset.markdownSegmentKey === renderKey) ?? null
    );
};

const escapeAttributeValue = (value: string): string =>
    value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

const mermaidTokensFor = (segment: RenderedMarkdownSegment): MarkdownResponseRenderToken[] =>
    segment.tokens.filter((token) => token.kind === 'mermaid-fullscreen');

const finalizePendingMermaid = async (): Promise<number> => {
    pruneRenderedMermaid();
    const pendingSegments = props.segments
        .map((segment) => ({
            segment,
            root: getSegmentRoot(segment.renderKey),
            tokens: mermaidTokensFor(segment).filter(
                (token) => !renderedMermaidElements.value.has(token.key),
            ),
        }))
        .filter(
            (entry): entry is typeof entry & { root: HTMLElement } =>
                entry.root !== null && entry.tokens.length > 0,
        );
    if (!pendingSegments.length) return 0;

    const selector = pendingSegments
        .map(
            ({ segment }) =>
                `[data-markdown-segment-key="${escapeAttributeValue(segment.renderKey)}"] pre.mermaid`,
        )
        .join(',');
    await props.renderMermaidCharts(selector);

    const next = new Map(renderedMermaidElements.value);
    for (const entry of pendingSegments) {
        if (getSegmentRoot(entry.segment.renderKey) !== entry.root) continue;
        const renderedBlocks = entry.root.querySelectorAll<HTMLElement>('.mermaid-wrapper > pre');
        entry.tokens.forEach((token, index) => {
            const block = renderedBlocks[index];
            const clone = block?.cloneNode(true);
            if (clone instanceof HTMLElement) next.set(token.key, clone);
        });
    }
    renderedMermaidElements.value = next;
    await nextTick();
    return pendingSegments.length;
};

watch(() => props.segments, pruneRenderedMermaid, { flush: 'sync' });

defineExpose({ finalizePendingMermaid });
</script>

<template>
    <div ref="responseRoot" style="display: contents">
        <div
            v-for="segment in segments"
            :key="segment.renderKey"
            :data-markdown-segment-key="segment.renderKey"
            style="display: contents"
        >
            <div
                data-markdown-response-html-segment
                style="display: contents"
                v-html="segment.html"
            />
            <Teleport
                v-for="token in segment.tokens"
                :key="token.key"
                defer
                :to="`#${token.targetId}`"
            >
                <GeneratedImageCard
                    v-if="token.kind === 'generated-image'"
                    :prompt="token.prompt"
                    :image-url="token.imageUrl"
                    @open-lightbox="emit('openLightbox', $event)"
                />
                <ToolQuestionCard
                    v-else-if="token.kind === 'tool-question'"
                    :tool-call-id="token.toolCallId"
                />
                <SandboxArtifactDownload
                    v-else-if="token.kind === 'sandbox-download'"
                    :file-id="token.fileId"
                    :label="token.label"
                    :filename="token.filename"
                    compact
                />
                <SandboxHtmlArtifactCard
                    v-else-if="token.kind === 'sandbox-html'"
                    :file-id="token.fileId"
                    :title="token.title"
                    :filename="token.filename"
                    :embed-url="`/api/files/embed/${token.fileId}?v=${HTML_EMBED_CACHE_BUSTER}`"
                    @send-prompt="emit('visualizerPrompt', $event)"
                />
                <VisualiseArtifactEmbed
                    v-else-if="token.kind === 'visualise'"
                    :file-id="token.fileId"
                    :caption="token.caption"
                    :embed-url="`/api/files/embed/${token.fileId}?v=${HTML_EMBED_CACHE_BUSTER}`"
                    @send-prompt="emit('visualizerPrompt', $event)"
                />
                <CopyButton
                    v-else-if="token.kind === 'code-copy'"
                    :text-to-copy="token.textToCopy"
                    :class="CONTROL_CLASS"
                />
                <FullScreenButton
                    v-else-if="
                        token.kind === 'mermaid-fullscreen' &&
                        renderedMermaidElements.get(token.key)
                    "
                    :rendered-element="renderedMermaidElements.get(token.key) ?? null"
                    :raw-mermaid-element="token.rawMermaidElement"
                    :class="CONTROL_CLASS"
                />
            </Teleport>
        </div>
    </div>
</template>
