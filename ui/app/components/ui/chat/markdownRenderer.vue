<script setup lang="ts">
import { createApp, h, onBeforeUnmount } from 'vue';
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import type { FileTreeNode, ExtractedIssue } from '@/types/github';
import type { ToolActivity, ToolCallArtifact, ToolCallDetail } from '@/types/toolCall';
import { useMarkdownProcessor } from '~/composables/useMarkdownProcessor';
import GeneratedImageCard from '~/components/ui/chat/utils/generatedImageCard.vue';
import SandboxArtifactDownload from '~/components/ui/chat/utils/sandboxArtifactDownload.vue';
import SandboxHtmlArtifactCard from '~/components/ui/chat/utils/sandboxHtmlArtifactCard.vue';
import ToolQuestionCard from '~/components/ui/chat/utils/toolQuestionCard.vue';
import VisualiseArtifactEmbed from '~/components/ui/chat/utils/visualiseArtifactEmbed.vue';

const emit = defineEmits(['rendered', 'edit-done', 'triggerScroll', 'visualizer-prompt']);

// --- Props ---
const props = withDefaults(
    defineProps<{
        message: Message;
        editMode: boolean;
        isStreaming?: boolean;
        isCollapsed?: boolean;
    }>(),
    {
        isStreaming: false,
        isCollapsed: false,
    },
);

// --- Plugins ---
const { $markedWorker } = useNuxtApp();

// --- Local State ---
const contentRef = ref<HTMLElement | null>(null);
type MountedAppRecord = {
    app: ReturnType<typeof createApp>;
    wrapper: HTMLElement;
};
const mountedImages = shallowRef<Map<string, MountedAppRecord>>(new Map());
const mountedSandboxDownloads = shallowRef<Map<string, MountedAppRecord>>(new Map());
const mountedToolQuestions = shallowRef<Map<string, MountedAppRecord>>(new Map());

// --- Composables ---
const { getTextFromMessage, getFilesFromMessage, getImageUrlsFromMessage } = useMessage();
const { error: showError } = useToast();
const { renderMermaidCharts } = useMermaid();
const {
    thinkingHtml,
    responseHtml,
    webSearches,
    fetchedPages,
    isError,
    processMarkdown,
    enhanceMermaidBlocks,
    enhanceCodeBlocks,
} = useMarkdownProcessor(contentRef as Ref<HTMLElement | null>);
const { fetchToolCallDetail } = useToolCallDetails();

// --- Computed ---
const isUserMessage = computed(() => {
    return props.message.role === MessageRoleEnum.user;
});

const COLLAPSE_THRESHOLD = 500;

const displayedUserText = computed(() => {
    const fullText = parseUserText(getTextFromMessage(props.message) || '');
    if (props.isCollapsed) {
        return `${fullText.substring(0, COLLAPSE_THRESHOLD)}...`;
    }
    return fullText;
});

// --- Image Generation Processing ---
interface ImageGenState {
    prompt: string;
    isGenerating: boolean;
    imageUrl?: string;
}

type MarkdownRendererPerfPhaseName =
    | 'preprocessMs'
    | 'markdownProcessorMs'
    | 'domEnhancementMs'
    | 'mermaidMs'
    | 'totalMs';

type MarkdownRendererPerfRun = {
    nodeId: string | null;
    parseId: number;
    markdownLength: number;
    isStreaming: boolean;
    status: 'completed' | 'empty' | 'stale';
    measures: Partial<Record<MarkdownRendererPerfPhaseName, number>>;
    startedAt: number;
    completedAt: number;
};

type MarkdownRendererPerfStore = {
    runs: MarkdownRendererPerfRun[];
    lastRun: MarkdownRendererPerfRun | null;
};

const activeImageGenerations = ref<ImageGenState[]>([]);
const toolActivities = ref<ToolActivity[]>([]);
const sandboxArtifacts = ref<ToolCallArtifact[]>([]);
const toolDetail = ref<ToolCallDetail | null>(null);
const isToolDetailOpen = ref(false);
const isToolDetailLoading = ref(false);
const hasSandboxExecution = ref(false);
let activeParseId = 0;
const PERF_MARK_NAMESPACE = 'markdown-renderer';
const ARTIFACT_TAG_REGEX =
    /<sandbox_artifact\s+tool_call_id="([^"]+)"\s+id="([^"]+)"\s+kind="([^"]+)"\s+name="([^"]*)"\s+path="([^"]*)"(?:\s+content_type="([^"]*)")?><\/sandbox_artifact>/g;
const SANDBOX_FILE_LINK_REGEX = /\[(.*?)\]\(sandbox-file:\/\/<?([0-9a-f-\s]{36,})>?\)/gi;
const SANDBOX_HTML_LINK_REGEX = /\[(.*?)\]\(sandbox-html:\/\/<?([0-9a-f-\s]{36,})>?\)/gi;
const VISUALISE_LINK_REGEX = /\[(.*?)\]\(visualise:\/\/<?([0-9a-f-\s]{36,})>?\)/gi;
const EXECUTING_CODE_TAG_REGEX =
    /<executing_code(?:\s+id="([^"]+)")?(?:\s+status="([^"]+)")?>([\s\S]*?)<\/executing_code>/g;
const ASKING_USER_TAG_REGEX = /<asking_user(?:\s+id="([^"]+)")?>([\s\S]*?)<\/asking_user>/g;

const TOOL_ACTIVITY_CONFIG: Array<{
    label: string;
    icon: string;
    pattern: RegExp;
    isError?: boolean;
    previewIndex?: number;
    statusIndex?: number;
}> = [
    {
        label: 'Generated image',
        icon: 'MdiImageMultipleOutline',
        pattern:
            /<generating_image(?:\s+id="([^"]+)")?>\s*Prompt:\s*"([^"]*)"\s*<\/generating_image>/g,
    },
    {
        label: 'Image generation error',
        icon: 'PhImageBroken',
        pattern:
            /<generating_image_error(?:\s+id="([^"]+)")?>([\s\S]*?)<\/generating_image_error>/g,
    },
    {
        label: 'Executed code',
        icon: 'MaterialSymbolsTerminalRounded',
        pattern: EXECUTING_CODE_TAG_REGEX,
        previewIndex: 3,
        statusIndex: 2,
    },
    {
        label: 'Mermaid diagram',
        icon: 'MaterialSymbolsAccountTreeOutlineRounded',
        pattern:
            /<generating_mermaid_diagram(?:\s+id="([^"]+)")?>([\s\S]*?)<\/generating_mermaid_diagram>/g,
    },
    {
        label: 'Mermaid generation error',
        icon: 'MaterialSymbolsAccountTreeOutlineRounded',
        pattern:
            /<generating_mermaid_diagram_error(?:\s+id="([^"]+)")?>([\s\S]*?)<\/generating_mermaid_diagram_error>/g,
    },
    {
        label: 'Visualised',
        icon: 'MaterialSymbolsBarChartRounded',
        pattern: /<visualising(?:\s+id="([^"]+)")?>([\s\S]*?)<\/visualising>/g,
    },
    {
        label: 'Visualise error',
        icon: 'MaterialSymbolsBarChartRounded',
        pattern: /<visualising_error(?:\s+id="([^"]+)")?>([\s\S]*?)<\/visualising_error>/g,
        isError: true,
    },
    {
        label: 'Asked user',
        icon: 'LucideMessageCircleDashed',
        pattern: ASKING_USER_TAG_REGEX,
    },
];

const extractToolActivities = (markdown: string): ToolActivity[] => {
    const matches: Array<ToolActivity & { index: number }> = [];

    for (const {
        label,
        icon,
        pattern,
        isError,
        previewIndex = 2,
        statusIndex,
    } of TOOL_ACTIVITY_CONFIG) {
        for (const match of markdown.matchAll(pattern)) {
            const toolCallId = match[1];
            const preview = (match[previewIndex] || '')
                .replace(ARTIFACT_TAG_REGEX, '')
                .trim()
                .replace(/\s+/g, ' ')
                .slice(0, 120);
            const derivedError =
                isError ||
                (statusIndex !== undefined && (match[statusIndex] || '').trim() === 'error');

            if (!toolCallId) {
                continue;
            }

            matches.push({
                index: match.index ?? 0,
                toolCallId,
                label,
                preview,
                icon,
                isError: derivedError,
            });
        }
    }

    return matches.sort((a, b) => a.index - b.index).map(({ index, ...tool }) => tool);
};

const decodeHtmlAttribute = (value: string): string => {
    return value
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&');
};

const encodeHtmlAttribute = (value: string): string => {
    return value
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
};

const normalizeArtifactLinkId = (value: string): string | null => {
    const normalized = value.replace(/\s+/g, '');
    return /^[0-9a-f-]{36}$/i.test(normalized) ? normalized : null;
};

const buildSandboxDownloadPlaceholder = (
    fileId: string,
    label: string,
    filename: string,
): string => {
    return `<div class="sandbox-download-placeholder" data-file-id="${fileId}" data-label="${encodeHtmlAttribute(label)}" data-filename="${encodeHtmlAttribute(filename)}"></div>`;
};

const buildSandboxHtmlPlaceholder = (fileId: string, title: string, filename: string): string => {
    return `<div class="sandbox-html-placeholder" data-file-id="${fileId}" data-title="${encodeHtmlAttribute(title)}" data-filename="${encodeHtmlAttribute(filename)}"></div>`;
};

const buildVisualisePlaceholder = (fileId: string, caption: string): string => {
    return `<div class="visualise-artifact-placeholder" data-file-id="${fileId}" data-caption="${encodeHtmlAttribute(caption)}"></div>`;
};

const buildToolQuestionPlaceholder = (toolCallId: string): string => {
    return `<div class="tool-question-placeholder" data-tool-call-id="${toolCallId}"></div>`;
};

const SANDBOX_HTML_PLACEHOLDER_REGEX =
    /<div class="sandbox-html-placeholder" data-file-id="([^"]+)" data-title="([^"]*)" data-filename="([^"]*)"><\/div>/g;
const VISUALISE_PLACEHOLDER_REGEX =
    /<div class="visualise-artifact-placeholder" data-file-id="([^"]+)" data-caption="([^"]*)"><\/div>/g;
const EMBED_PLACEHOLDER_REGEX = new RegExp(
    `${SANDBOX_HTML_PLACEHOLDER_REGEX.source}|${VISUALISE_PLACEHOLDER_REGEX.source}`,
    'g',
);

type ResponseSegment =
    | {
          key: string;
          type: 'html';
          html: string;
      }
    | {
          key: string;
          type: 'sandbox-html';
          fileId: string;
          title: string;
          filename: string;
      }
    | {
          key: string;
          type: 'visualise';
          fileId: string;
          caption: string;
      };

const renderedResponseSegments = computed<ResponseSegment[]>(() => {
    const html = responseHtml.value || '';
    if (!html) {
        return [];
    }

    const segments: ResponseSegment[] = [];
    let lastIndex = 0;
    let htmlIndex = 0;

    for (const match of html.matchAll(EMBED_PLACEHOLDER_REGEX)) {
        const matchIndex = match.index ?? 0;
        if (matchIndex > lastIndex) {
            const htmlChunk = html.slice(lastIndex, matchIndex);
            if (htmlChunk) {
                segments.push({
                    key: `html:${htmlIndex}`,
                    type: 'html',
                    html: htmlChunk,
                });
                htmlIndex += 1;
            }
        }

        if (match[1]) {
            segments.push({
                key: `sandbox-html:${match[1]}:${match[2]}:${match[3]}`,
                type: 'sandbox-html',
                fileId: match[1],
                title: decodeHtmlAttribute(match[2] || '').trim() || 'Interactive result',
                filename: decodeHtmlAttribute(match[3] || '').trim() || 'artifact.html',
            });
        } else if (match[4]) {
            segments.push({
                key: `visualise:${match[4]}:${match[5]}`,
                type: 'visualise',
                fileId: match[4],
                caption: decodeHtmlAttribute(match[5] || '').trim() || 'Interactive visual',
            });
        }

        lastIndex = matchIndex + match[0].length;
    }

    if (lastIndex < html.length) {
        const htmlChunk = html.slice(lastIndex);
        if (htmlChunk) {
            segments.push({
                key: `html:${htmlIndex}`,
                type: 'html',
                html: htmlChunk,
            });
        }
    }

    return segments;
});

const extractSandboxArtifacts = (markdown: string): ToolCallArtifact[] => {
    const artifacts: ToolCallArtifact[] = [];
    const seenIds = new Set<string>();

    ARTIFACT_TAG_REGEX.lastIndex = 0;
    for (const match of markdown.matchAll(ARTIFACT_TAG_REGEX)) {
        const toolCallId = match[1];
        const artifactId = match[2];
        const kind = match[3] === 'image' ? 'image' : 'file';
        const name = decodeHtmlAttribute(match[4] || '').trim();
        const relativePath = decodeHtmlAttribute(match[5] || '').trim();
        const contentType = decodeHtmlAttribute(match[6] || '').trim();

        if (!artifactId || !name || !relativePath || seenIds.has(artifactId)) {
            continue;
        }

        seenIds.add(artifactId);
        artifacts.push({
            tool_call_id: toolCallId,
            id: artifactId,
            kind,
            name,
            relative_path: relativePath,
            content_type:
                contentType || (kind === 'image' ? 'image/*' : 'application/octet-stream'),
            size: 0,
        });
    }

    return artifacts;
};

const hasSandboxExecutionCall = (markdown: string): boolean => {
    return markdown.includes('<executing_code');
};

const stripToolIndicators = (markdown: string): string => {
    return markdown
        .replace(ARTIFACT_TAG_REGEX, '')
        .replace(EXECUTING_CODE_TAG_REGEX, '')
        .replace(
            /<generating_mermaid_diagram(?:\s+id="[^"]+")?>[\s\S]*?<\/generating_mermaid_diagram>/g,
            '',
        )
        .replace(
            /<generating_mermaid_diagram_error(?:\s+id="[^"]+")?>[\s\S]*?<\/generating_mermaid_diagram_error>/g,
            '',
        )
        .replace(/<visualising(?:\s+id="[^"]+")?>[\s\S]*?<\/visualising>/g, '')
        .replace(/<visualising_error(?:\s+id="[^"]+")?>[\s\S]*?<\/visualising_error>/g, '');
};

const processSandboxDownloadLinks = (
    markdown: string,
    artifactsById: Map<string, ToolCallArtifact>,
): string => {
    SANDBOX_FILE_LINK_REGEX.lastIndex = 0;
    return markdown.replace(SANDBOX_FILE_LINK_REGEX, (_match, label: string, fileId: string) => {
        const normalizedFileId = normalizeArtifactLinkId(fileId);
        if (!normalizedFileId) {
            return _match;
        }

        const artifact = artifactsById.get(normalizedFileId);
        const resolvedLabel = label || artifact?.name || 'Download file';
        const resolvedFilename = artifact?.name || label || 'download';

        return buildSandboxDownloadPlaceholder(normalizedFileId, resolvedLabel, resolvedFilename);
    });
};

const processSandboxHtmlLinks = (
    markdown: string,
    artifactsById: Map<string, ToolCallArtifact>,
): string => {
    SANDBOX_HTML_LINK_REGEX.lastIndex = 0;
    return markdown.replace(SANDBOX_HTML_LINK_REGEX, (_match, label: string, fileId: string) => {
        const normalizedFileId = normalizeArtifactLinkId(fileId);
        if (!normalizedFileId) {
            return _match;
        }

        const artifact = artifactsById.get(normalizedFileId);
        const resolvedTitle = label || artifact?.name || 'Interactive result';
        const resolvedFilename = artifact?.name || label || 'artifact.html';
        return buildSandboxHtmlPlaceholder(normalizedFileId, resolvedTitle, resolvedFilename);
    });
};

const processVisualiseLinks = (
    markdown: string,
    artifactsById: Map<string, ToolCallArtifact>,
): string => {
    VISUALISE_LINK_REGEX.lastIndex = 0;
    return markdown.replace(VISUALISE_LINK_REGEX, (_match, label: string, fileId: string) => {
        const normalizedFileId = normalizeArtifactLinkId(fileId);
        if (!normalizedFileId) {
            return _match;
        }

        const artifact = artifactsById.get(normalizedFileId);
        const resolvedCaption = label || artifact?.name || 'Interactive visual';
        return buildVisualisePlaceholder(normalizedFileId, resolvedCaption);
    });
};

const processToolQuestions = (markdown: string): string => {
    ASKING_USER_TAG_REGEX.lastIndex = 0;
    return markdown.replace(ASKING_USER_TAG_REGEX, (_match, toolCallId: string) => {
        if (!toolCallId) {
            return '';
        }

        return `\n\n${buildToolQuestionPlaceholder(toolCallId)}\n\n`;
    });
};

const processImageGeneration = (markdown: string): string => {
    activeImageGenerations.value = [];
    let processedMarkdown = markdown;

    // 1. Detect Active Generation (Streaming)
    if (markdown.includes('[IMAGE_GEN]') && !markdown.includes('[!IMAGE_GEN]')) {
        const activeGenMatch = /<generating_image(?:\s+id="[^"]+")?>\s*Prompt:\s*"([^"]*)"/s;
        const match = markdown.match(activeGenMatch);

        activeImageGenerations.value.push({
            prompt: match?.[1] || 'Creating your image...',
            isGenerating: true,
        });
    }

    // 2. Clean up Helper Tags
    processedMarkdown = processedMarkdown
        .replace(/\[IMAGE_GEN\]/g, '')
        .replace(/\[!IMAGE_GEN\]/g, '')
        .replace(/<generating_image(?:\s+id="[^"]+")?>[\s\S]*?<\/generating_image>/g, '')
        .replace(
            /<generating_image_error(?:\s+id="[^"]+")?>[\s\S]*?<\/generating_image_error>/g,
            '',
        );

    // 3. Replace Markdown Images with Placeholders (only for Meridian-generated images with UUIDs)
    const markdownImageRegex = /!\[(.*?)\]\((.*?)\)/g;
    processedMarkdown = processedMarkdown.replace(
        markdownImageRegex,
        (_match, altText, imageUrl) => {
            const uuidRegex = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
            const match = imageUrl.match(uuidRegex);
            if (!match) {
                return _match;
            }
            const cleanUrl = `/api/files/view/${match[0]}`;
            const escapedPrompt = altText.replace(/"/g, '&quot;');
            return `<div class="generated-image-placeholder" data-prompt="${escapedPrompt}" data-image-url="${cleanUrl}"></div>`;
        },
    );

    return processedMarkdown;
};

const createPerfRecorder = (
    parseId: number,
    markdown: string,
): {
    mark: (label: string) => void;
    measure: (phaseName: MarkdownRendererPerfPhaseName, start: string, end: string) => void;
    finish: (status: MarkdownRendererPerfRun['status']) => void;
} | null => {
    if (!import.meta.dev || !import.meta.client || typeof performance === 'undefined') {
        return null;
    }

    const nodeId = props.message.node_id ?? null;
    const prefix = `${PERF_MARK_NAMESPACE}:${nodeId ?? 'unknown'}:${parseId}`;
    const marks = new Set<string>();
    const measures = new Set<string>();
    const run: MarkdownRendererPerfRun = {
        nodeId,
        parseId,
        markdownLength: markdown.length,
        isStreaming: props.isStreaming,
        status: 'completed',
        measures: {},
        startedAt: performance.now(),
        completedAt: performance.now(),
    };

    const getPerfStore = (): MarkdownRendererPerfStore => {
        const perfWindow = window as typeof window & {
            __markdownRendererPerf?: MarkdownRendererPerfStore;
        };

        if (!perfWindow.__markdownRendererPerf) {
            perfWindow.__markdownRendererPerf = {
                runs: [],
                lastRun: null,
            };
        }

        return perfWindow.__markdownRendererPerf;
    };

    const buildMarkName = (label: string) => `${prefix}:mark:${label}`;
    const buildMeasureName = (phaseName: MarkdownRendererPerfPhaseName) =>
        `${prefix}:measure:${phaseName}`;

    const mark = (label: string) => {
        const markName = buildMarkName(label);
        performance.mark(markName);
        marks.add(markName);
    };

    const measure = (phaseName: MarkdownRendererPerfPhaseName, start: string, end: string) => {
        const measureName = buildMeasureName(phaseName);
        performance.measure(measureName, buildMarkName(start), buildMarkName(end));
        measures.add(measureName);
        const duration = performance.getEntriesByName(measureName).at(-1)?.duration;
        if (duration !== undefined) {
            run.measures[phaseName] = Number(duration.toFixed(3));
        }
    };

    const finish = (status: MarkdownRendererPerfRun['status']) => {
        run.status = status;
        run.completedAt = performance.now();

        const perfStore = getPerfStore();
        perfStore.runs.push(run);
        perfStore.runs = perfStore.runs.slice(-500);
        if (status !== 'stale') {
            perfStore.lastRun = run;
        }

        for (const markName of marks) {
            performance.clearMarks(markName);
        }

        for (const measureName of measures) {
            performance.clearMeasures(measureName);
        }
    };

    mark('start');

    return {
        mark,
        measure,
        finish,
    };
};

// --- Core Logic Functions ---
const parseContent = async (markdown: string) => {
    const parseId = ++activeParseId;
    const normalizedMarkdown = markdown.trim();
    const perfRecorder = createPerfRecorder(parseId, normalizedMarkdown);

    if (isUserMessage.value) {
        toolActivities.value = [];
        sandboxArtifacts.value = [];
        hasSandboxExecution.value = false;
        emit('rendered');
        perfRecorder?.finish('stale');
        return;
    }

    hasSandboxExecution.value = hasSandboxExecutionCall(normalizedMarkdown);
    toolActivities.value = extractToolActivities(normalizedMarkdown);
    const extractedArtifacts = extractSandboxArtifacts(normalizedMarkdown);
    const artifactsById = new Map(extractedArtifacts.map((artifact) => [artifact.id, artifact]));
    sandboxArtifacts.value = extractedArtifacts;
    const strippedMarkdown = stripToolIndicators(normalizedMarkdown);

    perfRecorder?.mark('preprocess-end');
    perfRecorder?.measure('preprocessMs', 'start', 'preprocess-end');
    perfRecorder?.mark('markdown-processor-start');
    await processMarkdown(strippedMarkdown, $markedWorker.parse, (responseMarkdown) =>
        processSandboxDownloadLinks(
            processSandboxHtmlLinks(
                processVisualiseLinks(
                    processToolQuestions(processImageGeneration(responseMarkdown)),
                    artifactsById,
                ),
                artifactsById,
            ),
            artifactsById,
        ),
    );
    perfRecorder?.mark('markdown-processor-end');
    perfRecorder?.measure(
        'markdownProcessorMs',
        'markdown-processor-start',
        'markdown-processor-end',
    );
    if (parseId !== activeParseId) {
        perfRecorder?.finish('stale');
        return;
    }

    if (!normalizedMarkdown) {
        unmountImageApps();
        unmountSandboxDownloadApps();
        unmountToolQuestionApps();
        perfRecorder?.mark('dom-enhancement-start');
        perfRecorder?.mark('dom-enhancement-end');
        perfRecorder?.measure('domEnhancementMs', 'dom-enhancement-start', 'dom-enhancement-end');
        perfRecorder?.mark('complete');
        perfRecorder?.measure('totalMs', 'start', 'complete');
        perfRecorder?.finish('empty');
        if (!props.isStreaming) emit('rendered');
        else nextTick(() => emit('triggerScroll'));
        return;
    }

    if (isError.value && !thinkingHtml.value) {
        showError('Error rendering content. Please try again later.');
    }

    await nextTick();

    perfRecorder?.mark('dom-enhancement-start');
    enhanceCodeBlocks();
    enhanceGeneratedImages();
    enhanceSandboxDownloads();
    enhanceToolQuestions();
    perfRecorder?.mark('dom-enhancement-end');
    perfRecorder?.measure('domEnhancementMs', 'dom-enhancement-start', 'dom-enhancement-end');

    if (responseHtml.value.includes('<pre class="mermaid">')) {
        if (!props.isStreaming) {
            const container = contentRef.value;
            const mermaidBlocks = Array.from(container.querySelectorAll('pre.mermaid'));
            const rawMermaidElements = mermaidBlocks.map((block) => block.innerHTML);

            try {
                perfRecorder?.mark('mermaid-start');
                await renderMermaidCharts();
            } catch (err) {
                console.error('Mermaid rendering failed:', err);
            }
            enhanceMermaidBlocks(rawMermaidElements);
            perfRecorder?.mark('mermaid-end');
            perfRecorder?.measure('mermaidMs', 'mermaid-start', 'mermaid-end');
        }
    }

    perfRecorder?.mark('complete');
    perfRecorder?.measure('totalMs', 'start', 'complete');
    perfRecorder?.finish('completed');

    if (!props.isStreaming) emit('rendered');
    else nextTick(() => emit('triggerScroll'));
};

const openToolCallDetail = async (toolCallId: string) => {
    if (!toolCallId) {
        return;
    }

    try {
        isToolDetailLoading.value = true;
        isToolDetailOpen.value = true;
        toolDetail.value = await fetchToolCallDetail(toolCallId);
    } catch (error) {
        isToolDetailOpen.value = false;
        toolDetail.value = null;
        showError(`Failed to load tool call details: ${(error as Error).message}`);
    } finally {
        isToolDetailLoading.value = false;
    }
};

const closeToolCallDetail = () => {
    isToolDetailOpen.value = false;
};

// --- Image Enhancement ---
const lightboxImage = ref<{ src: string; prompt: string } | null>(null);

const handleOpenLightbox = (payload: { src: string; prompt: string }) => {
    lightboxImage.value = payload;
};

const enhanceGeneratedImages = () => {
    if (!contentRef.value) return;

    const placeholders = contentRef.value.querySelectorAll<HTMLElement>(
        '.generated-image-placeholder',
    );

    const currentUrls = new Set<string>();

    placeholders.forEach((placeholder) => {
        const { prompt, imageUrl } = placeholder.dataset;
        if (!prompt || !imageUrl) return;

        currentUrls.add(imageUrl);

        // If this image is already mounted, reattach the existing wrapper
        const existing = mountedImages.value.get(imageUrl);
        if (existing) {
            // Only reattach if not already a child of this placeholder
            if (existing.wrapper.parentElement !== placeholder) {
                placeholder.innerHTML = '';
                placeholder.appendChild(existing.wrapper);
            }
            return;
        }

        // New image: create a wrapper, mount the component, and track it
        const wrapper = document.createElement('div');
        placeholder.innerHTML = '';
        placeholder.appendChild(wrapper);

        const app = createApp({
            render: () =>
                h(GeneratedImageCard, {
                    prompt,
                    imageUrl,
                    onOpenLightbox: handleOpenLightbox,
                }),
        });

        app.mount(wrapper);
        mountedImages.value.set(imageUrl, { app, wrapper });
    });

    // Clean up images that are no longer in the content
    for (const [url, { app }] of mountedImages.value) {
        if (!currentUrls.has(url)) {
            app.unmount();
            mountedImages.value.delete(url);
        }
    }
};

const unmountImageApps = () => {
    for (const [, { app }] of mountedImages.value) {
        app.unmount();
    }
    mountedImages.value.clear();
};

const enhanceSandboxDownloads = () => {
    if (!contentRef.value) return;

    const placeholders = contentRef.value.querySelectorAll<HTMLElement>(
        '.sandbox-download-placeholder',
    );
    const currentKeys = new Set<string>();

    placeholders.forEach((placeholder) => {
        const { fileId, label, filename } = placeholder.dataset;
        if (!fileId || !label) return;

        const downloadKey = `${fileId}:${label}:${filename || ''}`;
        currentKeys.add(downloadKey);

        const existing = mountedSandboxDownloads.value.get(downloadKey);
        if (existing) {
            if (existing.wrapper.parentElement !== placeholder) {
                placeholder.innerHTML = '';
                placeholder.appendChild(existing.wrapper);
            }
            return;
        }

        const wrapper = document.createElement('div');
        placeholder.innerHTML = '';
        placeholder.appendChild(wrapper);

        const app = createApp({
            render: () =>
                h(SandboxArtifactDownload, {
                    fileId,
                    label,
                    filename: filename || label,
                    compact: true,
                }),
        });

        app.mount(wrapper);
        mountedSandboxDownloads.value.set(downloadKey, { app, wrapper });
    });

    for (const [key, { app }] of mountedSandboxDownloads.value) {
        if (!currentKeys.has(key)) {
            app.unmount();
            mountedSandboxDownloads.value.delete(key);
        }
    }
};

const unmountSandboxDownloadApps = () => {
    for (const [, { app }] of mountedSandboxDownloads.value) {
        app.unmount();
    }
    mountedSandboxDownloads.value.clear();
};

const enhanceToolQuestions = () => {
    if (!contentRef.value) return;

    const placeholders = contentRef.value.querySelectorAll<HTMLElement>(
        '.tool-question-placeholder',
    );
    const currentIds = new Set<string>();

    placeholders.forEach((placeholder) => {
        const { toolCallId } = placeholder.dataset;
        if (!toolCallId) return;

        currentIds.add(toolCallId);

        const existing = mountedToolQuestions.value.get(toolCallId);
        if (existing) {
            if (existing.wrapper.parentElement !== placeholder) {
                placeholder.innerHTML = '';
                placeholder.appendChild(existing.wrapper);
            }
            return;
        }

        const wrapper = document.createElement('div');
        placeholder.innerHTML = '';
        placeholder.appendChild(wrapper);

        const app = createApp({
            render: () =>
                h(ToolQuestionCard, {
                    toolCallId,
                }),
        });

        app.mount(wrapper);
        mountedToolQuestions.value.set(toolCallId, { app, wrapper });
    });

    for (const [toolCallId, { app }] of mountedToolQuestions.value) {
        if (!currentIds.has(toolCallId)) {
            app.unmount();
            mountedToolQuestions.value.delete(toolCallId);
        }
    }
};

const unmountToolQuestionApps = () => {
    for (const [, { app }] of mountedToolQuestions.value) {
        app.unmount();
    }
    mountedToolQuestions.value.clear();
};

const closeLightbox = () => {
    lightboxImage.value = null;
};

// --- Logic for User Messages ---
const extractedGithubFiles = ref<FileTreeNode[]>([]);
const extractedGithubIssues = ref<ExtractedIssue[]>([]);

const parseUserText = (content: string) => {
    extractedGithubFiles.value = [];
    extractedGithubIssues.value = [];

    // 1. Extract Files
    const fileRegex = /--- Start of file: (.+?) ---([\s\S]*?)--- End of file: \1 ---/g;
    let cleaned = content.replace(fileRegex, (_match, filename: string, fileContent: string) => {
        const file = {
            name: filename.trim().split('/').pop() || '',
            path: filename.trim(),
            type: 'file',
            content: fileContent.trim(),
            children: [],
        } as FileTreeNode;

        extractedGithubFiles.value.push(file);
        return '';
    });

    // 2. Extract Issues/PRs
    const issueRegex =
        /--- Start of (Issue|Pull Request) #(\d+): (.+?) ---\nAuthor: (.+?)\nState: (.+?)\nLink: (.+?)\n\n([\s\S]*?)--- End of \1 ---/g;
    cleaned = cleaned.replace(
        issueRegex,
        (_match, type, number, title, author, state, url, body) => {
            extractedGithubIssues.value.push({
                type: type as 'Issue' | 'Pull Request',
                number,
                title,
                author,
                state,
                url,
                content: body.trim(),
            });
            return '';
        },
    );

    // 3. Remove Node IDs
    const nodeIdRegex = /--- Node ID: [a-f0-9-]+ ---/g;
    const cleanedWithoutNodeIds = cleaned.replace(nodeIdRegex, '');

    return cleanedWithoutNodeIds.trim();
};

const getEditZones = (content: string): Record<string, string> => {
    const zones: Record<string, string> = {};
    const nodeIdRegex = /--- Node ID: ([a-f0-9-]+) ---/g;
    let lastIndex = 0;
    let lastNodeId: string | null = null;

    content.replace(nodeIdRegex, (match, nodeId, offset) => {
        if (lastNodeId) {
            zones[lastNodeId] = content.slice(lastIndex, offset).trim();
        }
        lastNodeId = nodeId;
        lastIndex = offset + match.length;
        return match;
    });

    if (lastNodeId) {
        zones[lastNodeId] = content.slice(lastIndex).trim();
    }

    return zones;
};

const handlePaste = (event: ClipboardEvent) => {
    event.preventDefault();
    const text = event.clipboardData?.getData('text/plain');
    if (!text) return;
    document.execCommand('insertText', false, text);
};

// --- Streaming throttle ---
const STREAMING_THROTTLE_MS = 80;
let streamingThrottleHandle: ReturnType<typeof setTimeout> | null = null;
let lastStreamingParseTime = 0;

// --- Watchers ---
watch(
    () => props.message,
    (newMessage) => {
        const text = getTextFromMessage(newMessage) || '';

        if (!props.isStreaming) {
            // Non-streaming: parse immediately, clear any pending throttle
            if (streamingThrottleHandle !== null) {
                clearTimeout(streamingThrottleHandle);
                streamingThrottleHandle = null;
            }
            lastStreamingParseTime = 0;
            parseContent(text);
            return;
        }

        // Streaming: leading + trailing throttle.
        // First chunk parses immediately, subsequent chunks throttled to ~80ms.
        const now = performance.now();
        const elapsed = now - lastStreamingParseTime;

        if (elapsed >= STREAMING_THROTTLE_MS) {
            lastStreamingParseTime = now;
            if (streamingThrottleHandle !== null) {
                clearTimeout(streamingThrottleHandle);
                streamingThrottleHandle = null;
            }
            parseContent(text);
        } else if (streamingThrottleHandle === null) {
            // Schedule a trailing parse using the latest value when it fires
            const remaining = STREAMING_THROTTLE_MS - elapsed;
            streamingThrottleHandle = setTimeout(() => {
                streamingThrottleHandle = null;
                lastStreamingParseTime = performance.now();
                parseContent(getTextFromMessage(props.message) || '');
            }, remaining);
        }
    },
    { deep: true },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    if (!isUserMessage.value) {
        parseContent(getTextFromMessage(props.message));
    } else {
        toolActivities.value = [];
        emit('rendered');
    }
});

// CRITICAL: Clean up mounted apps when the component is destroyed to prevent memory leaks.
onBeforeUnmount(() => {
    if (streamingThrottleHandle !== null) {
        clearTimeout(streamingThrottleHandle);
        streamingThrottleHandle = null;
    }
    unmountImageApps();
    unmountSandboxDownloadApps();
    unmountToolQuestionApps();
});
</script>

<template>
    <div
        v-if="isError"
        class="flex items-center gap-2 rounded-lg border-2 border-red-500/20 bg-red-500/20 p-2"
    >
        <UiIcon name="MaterialSymbolsErrorCircleRounded" class="h-8 w-8 shrink-0 text-red-500" />
        <p class="text-red-500">{{ responseHtml }}</p>
    </div>

    <!-- Loader -->
    <div
        v-if="!isUserMessage && !getTextFromMessage(props.message) && isStreaming"
        class="flex h-7 items-center"
    >
        <span class="loader relative inline-block h-7 w-7" />
        <span
            v-if="
                props.message.type === NodeTypeEnum.PARALLELIZATION ||
                props.message.type === NodeTypeEnum.PARALLELIZATION_MODELS
            "
            class="text-stone-gray ml-2 text-sm"
        >
            Fetching parallelization data...
        </span>
    </div>

    <!-- Assistant thinking response -->
    <div
        v-else-if="
            thinkingHtml ||
            (props.message.type === NodeTypeEnum.PARALLELIZATION && !props.isStreaming)
        "
        class="custom_scroll grid h-fit w-full grid-rows-[auto_auto] overflow-x-auto"
        :class="{
            'grid-cols-[10rem_calc(100%-10rem)]': thinkingHtml,
            'grid-cols-[1fr]': props.message.type === NodeTypeEnum.PARALLELIZATION && !thinkingHtml,
        }"
    >
        <UiChatThinkingDisclosure
            v-if="thinkingHtml"
            :thinking-html="thinkingHtml"
            :is-streaming="props.isStreaming"
            @trigger-scroll="emit('triggerScroll')"
        />

        <UiChatParallelizationDisclosure
            v-if="props.message.type === NodeTypeEnum.PARALLELIZATION"
            :data="props.message.data"
            :node-type="props.message.type"
            :is-streaming="props.isStreaming"
        />
    </div>

    <!-- Web Search Results -->
    <UiChatUtilsWebSearch
        v-for="search in webSearches"
        :key="`${search.toolCallId || 'search'}-${search.query}`"
        :web-search="search"
        @open-details="openToolCallDetail"
    />

    <!-- Fetched Page Content -->
    <UiChatUtilsFetchedPage
        v-if="fetchedPages.length"
        :fetched-pages="fetchedPages"
        @open-details="openToolCallDetail"
    />

    <div
        v-if="toolActivities.length && !isUserMessage && !isError"
        data-testid="markdown-renderer-tool-activities"
        class="mt-1 flex flex-col"
    >
        <div
            v-for="tool in toolActivities"
            :key="tool.toolCallId"
            :title="tool.preview ? `${tool.label}: ${tool.preview}` : tool.label"
            class="dark:text-soft-silk/80 text-obsidian mb-2 flex h-9 max-w-full items-center gap-2
                overflow-hidden rounded-lg transition-colors duration-200 ease-in-out"
        >
            <UiIcon
                :name="tool.icon"
                :class="['h-4 w-4 shrink-0', tool.isError ? 'text-red-500' : '']"
            />
            <div
                class="flex max-w-full min-w-0 items-center gap-1 overflow-hidden text-sm font-bold"
            >
                <span class="shrink-0">{{ tool.label }}</span>
                <span
                    v-if="tool.preview"
                    class="dark:text-soft-silk text-obsidian overflow-hidden text-ellipsis
                        whitespace-nowrap italic"
                >
                    {{ tool.preview }}
                </span>
            </div>
            <button
                class="hover:bg-stone-gray/10 mb-0.5 ml-2 flex items-center justify-center
                    rounded-md p-1.5 transition-colors duration-200"
                @click="openToolCallDetail(tool.toolCallId)"
            >
                <UiIcon name="MajesticonsInformationCircleLine" class="h-4 w-4" />
            </button>
        </div>
    </div>

    <!-- Final Assistant Response -->
    <template v-if="!isUserMessage && !isError">
        <div
            ref="contentRef"
            data-testid="markdown-renderer-response"
            :class="{
                'hide-code-scrollbar': isStreaming,
            }"
            class="prose prose-invert custom_scroll mt-4 min-w-full overflow-x-auto
                overflow-y-hidden"
        >
            <template v-for="segment in renderedResponseSegments" :key="segment.key">
                <div
                    v-if="segment.type === 'html'"
                    style="display: contents"
                    v-html="segment.html"
                />
                <SandboxHtmlArtifactCard
                    v-else-if="segment.type === 'sandbox-html'"
                    :file-id="segment.fileId"
                    :title="segment.title"
                    :filename="segment.filename"
                    :embed-url="`/api/files/embed/${segment.fileId}`"
                    @send-prompt="emit('visualizer-prompt', $event)"
                />
                <VisualiseArtifactEmbed
                    v-else
                    :file-id="segment.fileId"
                    :embed-url="`/api/files/embed/${segment.fileId}`"
                    :caption="segment.caption"
                    @send-prompt="emit('visualizer-prompt', $event)"
                />
            </template>
        </div>
        <UiChatUtilsSandboxArtifactsTray
            v-if="hasSandboxExecution && sandboxArtifacts.length"
            :artifacts="sandboxArtifacts"
            :is-streaming="props.isStreaming"
        />
    </template>

    <!-- For the user, just show the original content and associated files -->
    <div v-else-if="!isError">
        <div class="mb-1 flex w-fit flex-col gap-2 whitespace-pre-wrap">
            <UiChatAttachmentImages :images="getImageUrlsFromMessage(props.message)" />
            <UiChatAttachmentFiles :files="getFilesFromMessage(props.message)" />
        </div>

        <div v-if="editMode" class="flex w-full flex-col gap-2">
            <div
                v-for="(text, nodeId) in getEditZones(getTextFromMessage(props.message))"
                :key="nodeId"
                class="prose prose-invert bg-obsidian/25 text-soft-silk w-full max-w-none rounded-lg
                    px-2 py-1 whitespace-pre-wrap focus:outline-none"
                contenteditable
                autofocus
                @keydown.enter.exact.prevent="
                    emit('edit-done', nodeId, ($event.target as HTMLElement).innerText)
                "
                @paste="handlePaste"
            >
                {{ text }}
            </div>
        </div>

        <div
            v-else
            class="prose prose-invert text-soft-silk max-w-none overflow-hidden whitespace-pre-wrap"
        >
            {{ displayedUserText }}
            <UiChatGithubFileChatInlineGroup
                :extracted-github-files="extractedGithubFiles"
                :extracted-github-issues="extractedGithubIssues"
            />
        </div>
    </div>

    <!-- Image Generation Loaders -->
    <UiChatUtilsGeneratedImageLoader :active-image-generations="activeImageGenerations" />

    <!-- Lightbox Modal -->
    <UiChatUtilsGeneratedImageLightbox
        :lightbox-image="lightboxImage"
        @close-lightbox="closeLightbox"
    />
    <UiChatUtilsToolCallDetailModal
        :is-open="isToolDetailOpen"
        :is-loading="isToolDetailLoading"
        :detail="toolDetail"
        @close="closeToolCallDetail"
    />
</template>

<style scoped>
/* Basic Loader */
.loader::after,
.loader::before {
    content: '';
    box-sizing: border-box;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #fff;
    position: absolute;
    left: 0;
    top: 0;
    animation: animloader 2s linear infinite;
}
.loader::before {
    animation-delay: -1s;
}
@keyframes animloader {
    0% {
        transform: scale(0);
        opacity: 1;
    }
    100% {
        transform: scale(1);
        opacity: 0;
    }
}
</style>
