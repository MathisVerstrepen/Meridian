<script setup lang="ts">
import { onBeforeUnmount, useId } from 'vue';
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum, ToolEnum } from '@/types/enums';
import type { FileTreeNode, ExtractedIssue } from '@/types/github';
import type {
    FetchedPageDetailSelection,
    ToolActivity,
    ToolCallArtifact,
    ToolCallDetail,
} from '@/types/toolCall';
import { useMarkdownProcessor } from '~/composables/useMarkdownProcessor';
import MarkdownResponse from '~/components/ui/chat/markdownResponse.vue';
import {
    prepareMarkdownResponseContent,
    type ImageGenState,
} from '~/utils/markdownResponseContent';
import { prepareMarkdownResponse } from '~/utils/markdownResponseTokens';

const emit = defineEmits([
    'rendered',
    'edit-done',
    'cancel-edit',
    'triggerScroll',
    'visualizer-prompt',
]);

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
const markdownResponseRef = ref<InstanceType<typeof MarkdownResponse> | null>(null);
const markdownResponseScope = `markdown-response-${useId().replace(/[^a-zA-Z0-9_-]/g, '-')}`;
const editZoneDrafts = ref<Record<string, string>>({});
const activeEditNodeId = ref<string | null>(null);
const lightboxImage = ref<{ src: string; prompt: string } | null>(null);
const handleOpenLightbox = (payload: { src: string; prompt: string }) => {
    lightboxImage.value = payload;
};

// --- Composables ---
const { getTextFromMessage, getFilesFromMessage, getImageUrlsFromMessage } = useMessage();
const { error: showError } = useToast();
const { renderMermaidCharts } = useMermaid();
const {
    thinkingSegments,
    responseSegments,
    thinkingHtml,
    responseHtml,
    autoToolSelection,
    webSearches,
    fetchedPages,
    isError,
    processMarkdown,
} = useMarkdownProcessor();
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

const editZones = computed(() => {
    return getEditZones(getTextFromMessage(props.message));
});

const autoToolSelectionDisplay = computed(() => {
    if (isUserMessage.value || !autoToolSelection.value) {
        return null;
    }

    const tools = autoToolSelection.value.selectedTools.map(
        (tool) => AUTO_TOOL_SELECTION_TOOL_META[tool],
    );

    return { tools };
});

// --- Image Generation Processing ---
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
    parsedSegmentCount?: number;
    reusedSegmentCount?: number;
    enhancedSegmentCount?: number;
};

type MarkdownRendererPerfStore = {
    runs: MarkdownRendererPerfRun[];
    lastRun: MarkdownRendererPerfRun | null;
};

type AutoToolSelectionDisplayTool = {
    tool: ToolEnum;
    label: string;
    icon: string;
};

const AUTO_TOOL_SELECTION_TOOL_META = {
    [ToolEnum.WEB_SEARCH]: {
        tool: ToolEnum.WEB_SEARCH,
        label: 'Web Search',
        icon: 'MdiWeb',
    },
    [ToolEnum.LINK_EXTRACTION]: {
        tool: ToolEnum.LINK_EXTRACTION,
        label: 'Link Extraction',
        icon: 'MdiLinkVariant',
    },
    [ToolEnum.IMAGE_GENERATION]: {
        tool: ToolEnum.IMAGE_GENERATION,
        label: 'Image Generation',
        icon: 'MdiImageMultipleOutline',
    },
    [ToolEnum.EXECUTE_CODE]: {
        tool: ToolEnum.EXECUTE_CODE,
        label: 'Execute Code',
        icon: 'MaterialSymbolsTerminalRounded',
    },
    [ToolEnum.VISUALISE]: {
        tool: ToolEnum.VISUALISE,
        label: 'Visualise',
        icon: 'MaterialSymbolsBarChartRounded',
    },
    [ToolEnum.ASK_USER]: {
        tool: ToolEnum.ASK_USER,
        label: 'Ask User',
        icon: 'LucideMessageCircleDashed',
    },
} satisfies Record<ToolEnum, AutoToolSelectionDisplayTool>;

const activeImageGenerations = ref<ImageGenState[]>([]);
const toolActivities = ref<ToolActivity[]>([]);
const hasAskedUserActivity = computed(() =>
    toolActivities.value.some((activity) => activity.label === 'Asked user'),
);
const sandboxArtifacts = ref<ToolCallArtifact[]>([]);
const toolDetail = ref<ToolCallDetail | null>(null);
const fetchedPageSelection = ref<FetchedPageDetailSelection | null>(null);
const isToolDetailOpen = ref(false);
const isToolDetailLoading = ref(false);
const hasSandboxExecution = ref(false);
let activeParseId = 0;
const PERF_MARK_NAMESPACE = 'markdown-renderer';
const ARTIFACT_TAG_REGEX =
    /<sandbox_artifact\s+tool_call_id="([^"]+)"\s+id="([^"]+)"\s+kind="([^"]+)"\s+name="([^"]*)"\s+path="([^"]*)"(?:\s+content_type="([^"]*)")?><\/sandbox_artifact>/g;
const EXECUTING_CODE_TAG_REGEX =
    /<executing_code([^>]*)>([\s\S]*?)<\/executing_code>/g;
const ASKING_USER_TAG_REGEX = /<asking_user([^>]*)>([\s\S]*?)<\/asking_user>/g;
const TOOL_CALL_ID_ATTR_REGEX = /\bid="([^"]+)"/;
const TOOL_DURATION_ATTR_REGEX = /\bduration_ms="(\d+)"/;
const TOOL_STATUS_ATTR_REGEX = /\bstatus="([^"]+)"/;

const TOOL_ACTIVITY_CONFIG: Array<{
    label: string;
    icon: string;
    pattern: RegExp;
    isError?: boolean;
    previewIndex?: number;
}> = [
    {
        label: 'Generated image',
        icon: 'MdiImageMultipleOutline',
        pattern: /<generating_image([^>]*)>\s*Prompt:\s*"([^"]*)"\s*<\/generating_image>/g,
    },
    {
        label: 'Image generation error',
        icon: 'PhImageBroken',
        pattern: /<generating_image_error([^>]*)>([\s\S]*?)<\/generating_image_error>/g,
    },
    {
        label: 'Generated video',
        icon: 'MaterialSymbolsVideoCameraBackRounded',
        pattern: /<generating_video([^>]*)>\s*Prompt:\s*"([^"]*)"\s*<\/generating_video>/g,
    },
    {
        label: 'Video generation error',
        icon: 'MaterialSymbolsVideoCameraBackRounded',
        pattern: /<generating_video_error([^>]*)>([\s\S]*?)<\/generating_video_error>/g,
        isError: true,
    },
    {
        label: 'Executed code',
        icon: 'MaterialSymbolsTerminalRounded',
        pattern: EXECUTING_CODE_TAG_REGEX,
        previewIndex: 2,
    },
    {
        label: 'Mermaid diagram',
        icon: 'MaterialSymbolsAccountTreeOutlineRounded',
        pattern: /<generating_mermaid_diagram([^>]*)>([\s\S]*?)<\/generating_mermaid_diagram>/g,
    },
    {
        label: 'Mermaid generation error',
        icon: 'MaterialSymbolsAccountTreeOutlineRounded',
        pattern:
            /<generating_mermaid_diagram_error([^>]*)>([\s\S]*?)<\/generating_mermaid_diagram_error>/g,
    },
    {
        label: 'Visualised',
        icon: 'MaterialSymbolsBarChartRounded',
        pattern: /<visualising([^>]*)>([\s\S]*?)<\/visualising>/g,
    },
    {
        label: 'Visualise error',
        icon: 'MaterialSymbolsBarChartRounded',
        pattern: /<visualising_error([^>]*)>([\s\S]*?)<\/visualising_error>/g,
        isError: true,
    },
    {
        label: 'Asked user',
        icon: 'LucideMessageCircleDashed',
        pattern: ASKING_USER_TAG_REGEX,
    },
];

const extractToolCallId = (attributes: string): string | null => {
    return TOOL_CALL_ID_ATTR_REGEX.exec(attributes)?.[1] || null;
};

const extractToolDurationMs = (attributes: string): number | undefined => {
    const rawValue = TOOL_DURATION_ATTR_REGEX.exec(attributes)?.[1];
    if (!rawValue) {
        return undefined;
    }

    const durationMs = Number.parseInt(rawValue, 10);
    return Number.isFinite(durationMs) ? durationMs : undefined;
};

const extractToolStatus = (attributes: string): string | undefined => {
    return TOOL_STATUS_ATTR_REGEX.exec(attributes)?.[1];
};

const formatToolDuration = (durationMs: number): string => {
    if (durationMs < 1000) {
        return `${durationMs} ms`;
    }

    const totalSeconds = Math.round(durationMs / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
        return `${hours}h ${minutes}m ${seconds}s`;
    }

    if (minutes > 0) {
        return `${minutes}m ${seconds}s`;
    }

    return `${seconds}s`;
};

const extractToolActivities = (markdown: string): ToolActivity[] => {
    const matches: Array<ToolActivity & { index: number }> = [];

    for (const { label, icon, pattern, isError, previewIndex = 2 } of TOOL_ACTIVITY_CONFIG) {
        for (const match of markdown.matchAll(pattern)) {
            const attributes = match[1] || '';
            const toolCallId = extractToolCallId(attributes);
            const durationMs = extractToolDurationMs(attributes);
            const preview = (match[previewIndex] || '')
                .replace(ARTIFACT_TAG_REGEX, '')
                .trim()
                .replace(/\s+/g, ' ')
                .slice(0, 120);
            const derivedError = isError || extractToolStatus(attributes)?.trim() === 'error';

            if (!toolCallId) {
                continue;
            }

            matches.push({
                index: match.index ?? 0,
                toolCallId,
                durationMs,
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
            /<generating_mermaid_diagram(?:\s+[^>]*)?>[\s\S]*?<\/generating_mermaid_diagram>/g,
            '',
        )
        .replace(
            /<generating_mermaid_diagram_error(?:\s+[^>]*)?>[\s\S]*?<\/generating_mermaid_diagram_error>/g,
            '',
        )
        .replace(/<visualising(?:\s+[^>]*)?>[\s\S]*?<\/visualising>/g, '')
        .replace(/<visualising_error(?:\s+[^>]*)?>[\s\S]*?<\/visualising_error>/g, '')
        .replace(/<generating_video(?:\s+[^>]*)?>[\s\S]*?<\/generating_video>/g, '')
        .replace(
            /<generating_video_error(?:\s+[^>]*)?>[\s\S]*?<\/generating_video_error>/g,
            '',
        );
};

const createPerfRecorder = (
    parseId: number,
    markdown: string,
): {
    mark: (label: string) => void;
    measure: (phaseName: MarkdownRendererPerfPhaseName, start: string, end: string) => void;
    recordSegmentCounts: (counts: {
        parsedSegmentCount: number;
        reusedSegmentCount: number;
        enhancedSegmentCount: number;
    }) => void;
    finish: (status: MarkdownRendererPerfRun['status']) => void;
} | null => {
    if (!import.meta.dev || !import.meta.client || isRuntimeUndefined(performance)) {
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
        if (!window.__markdownRendererPerf) {
            window.__markdownRendererPerf = {
                runs: [],
                lastRun: null,
            };
        }

        return window.__markdownRendererPerf;
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
        recordSegmentCounts: (counts) => Object.assign(run, counts),
        finish,
    };
};

// --- Core Logic Functions ---
let lastMessageIdentity = props.message;
let messageIdentityRevision = 0;

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
    sandboxArtifacts.value = extractedArtifacts;
    const strippedMarkdown = stripToolIndicators(normalizedMarkdown);

    perfRecorder?.mark('preprocess-end');
    perfRecorder?.measure('preprocessMs', 'start', 'preprocess-end');
    perfRecorder?.mark('markdown-processor-start');
    if (lastMessageIdentity !== props.message) {
        lastMessageIdentity = props.message;
        messageIdentityRevision += 1;
    }
    const processResult = await processMarkdown(
        strippedMarkdown,
        $markedWorker.parse,
        (responseMarkdown) => {
            const prepared = prepareMarkdownResponseContent(responseMarkdown, extractedArtifacts);
            activeImageGenerations.value = prepared.activeImageGenerations;
            return prepared.markdown;
        },
        {
            cacheKey: `${messageIdentityRevision}:${props.message.role}:${props.message.node_id ?? ''}:${props.message.type}`,
            isStreaming: props.isStreaming,
            responseHtmlPreparer: (html, renderKey) =>
                prepareMarkdownResponse(html, `${markdownResponseScope}-${renderKey}`),
        },
    );
    perfRecorder?.mark('markdown-processor-end');
    perfRecorder?.measure(
        'markdownProcessorMs',
        'markdown-processor-start',
        'markdown-processor-end',
    );
    if (parseId !== activeParseId || !processResult.committed) {
        perfRecorder?.finish('stale');
        return;
    }

    if (!normalizedMarkdown) {
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
    const enhancedSegmentCount = processResult.changedResponseRenderKeys.length;
    perfRecorder?.mark('dom-enhancement-end');
    perfRecorder?.measure('domEnhancementMs', 'dom-enhancement-start', 'dom-enhancement-end');

    if (!props.isStreaming) {
        try {
            perfRecorder?.mark('mermaid-start');
            await markdownResponseRef.value?.finalizePendingMermaid();
        } catch (err) {
            console.error('Mermaid rendering failed:', err);
        }
        perfRecorder?.mark('mermaid-end');
        perfRecorder?.measure('mermaidMs', 'mermaid-start', 'mermaid-end');
    }

    perfRecorder?.recordSegmentCounts({
        parsedSegmentCount: processResult.parsedSegmentCount,
        reusedSegmentCount: processResult.reusedSegmentCount,
        enhancedSegmentCount,
    });

    perfRecorder?.mark('complete');
    perfRecorder?.measure('totalMs', 'start', 'complete');
    perfRecorder?.finish('completed');

    if (!props.isStreaming) emit('rendered');
    else nextTick(() => emit('triggerScroll'));
};

const openToolCallDetail = async (
    toolCallId: string,
    selection: FetchedPageDetailSelection | null = null,
) => {
    fetchedPageSelection.value = selection;
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
        fetchedPageSelection.value = null;
        showError(`Failed to load tool call details: ${runtimeErrorMessage(error)}`);
    } finally {
        isToolDetailLoading.value = false;
    }
};

const closeToolCallDetail = () => {
    isToolDetailOpen.value = false;
    fetchedPageSelection.value = null;
};

const closeLightbox = () => {
    lightboxImage.value = null;
};

// --- Logic for User Messages ---
interface ExtractedFileTreeNode extends FileTreeNode {
    content: string;
}

const extractedGithubFiles = ref<ExtractedFileTreeNode[]>([]);
const extractedGithubIssues = ref<ExtractedIssue[]>([]);

const parseUserText = (content: string) => {
    extractedGithubFiles.value = [];
    extractedGithubIssues.value = [];

    // 1. Extract Files
    const fileRegex = /--- Start of file: (.+?) ---([\s\S]*?)--- End of file: \1 ---/g;
    let cleaned = content.replace(fileRegex, (_match, filename: string, fileContent: string) => {
        const file: ExtractedFileTreeNode = {
            name: filename.trim().split('/').pop() || '',
            path: filename.trim(),
            type: 'file',
            content: fileContent.trim(),
            children: [],
        };

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
                type: type === 'Issue' ? 'Issue' : 'Pull Request',
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

const getEditZones = (content: string) => {
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

    const fallbackNodeId = props.message.prompt_node_id ?? props.message.node_id;
    if (Object.keys(zones).length === 0 && fallbackNodeId) {
        zones[fallbackNodeId] = content.trim();
    }

    return zones;
};

const handlePaste = (event: ClipboardEvent) => {
    event.preventDefault();
    const text = event.clipboardData?.getData('text/plain');
    if (!text) return;
    document.execCommand('insertText', false, text);

    const target = elementOrNull(event.target, HTMLElement);
    if (activeEditNodeId.value && target) {
        editZoneDrafts.value[activeEditNodeId.value] = target.innerText;
    }
};

const resetEditDrafts = () => {
    editZoneDrafts.value = { ...editZones.value };
    activeEditNodeId.value = Object.keys(editZones.value)[0] ?? null;
};

const handleEditInput = (nodeId: string, event: Event) => {
    editZoneDrafts.value[nodeId] = (requireElement(event.target, HTMLElement)).innerText;
};

const submitEdit = (nodeId = activeEditNodeId.value) => {
    const targetNodeId = nodeId ?? Object.keys(editZoneDrafts.value)[0];
    if (!targetNodeId) return;

    emit('edit-done', targetNodeId, editZoneDrafts.value[targetNodeId] ?? '');
};

defineExpose({ submitEdit });

// --- Streaming throttle ---
const STREAMING_THROTTLE_MS = 80;
let streamingThrottleHandle: ReturnType<typeof setTimeout> | null = null;
let lastStreamingParseTime = 0;

// --- Watchers ---
const messageTextRevision = computed(() => getTextFromMessage(props.message) || '');

watch(
    [
        () => props.message,
        () => props.message.role,
        () => props.message.node_id,
        () => props.message.type,
        messageTextRevision,
        () => props.isStreaming,
    ],
    ([, , , , text, isStreaming]) => {
        if (!isStreaming) {
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
                parseContent(messageTextRevision.value);
            }, remaining);
        }
    },
);

watch(
    [() => props.editMode, editZones],
    ([isEditMode]) => {
        if (isEditMode) {
            resetEditDrafts();
        }
    },
    { immediate: true },
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

    <div
        v-if="autoToolSelectionDisplay && !isUserMessage && !isError"
        class="mb-3 flex flex-wrap items-center gap-1.5 rounded-lg border border-stone-gray/10
            bg-anthracite/20 px-2 py-1.5"
    >
        <div
            class="dark:text-soft-silk/80 text-obsidian inline-flex items-center gap-1 text-xs
                font-bold"
        >
            <UiIcon name="MynauiSparklesSolid" class="h-3.5 w-3.5 shrink-0" />
            <span>Auto-selected</span>
        </div>
        <template v-if="autoToolSelectionDisplay.tools.length">
            <div
                v-for="tool in autoToolSelectionDisplay.tools"
                :key="tool.tool"
                class="dark:bg-soft-silk/8 dark:text-soft-silk/80 text-obsidian inline-flex items-center
                    gap-1 rounded-full bg-black/5 px-2 py-0.5 text-[11px] font-semibold"
            >
                <UiIcon :name="tool.icon" class="h-3.5 w-3.5 shrink-0" />
                <span>{{ tool.label }}</span>
            </div>
        </template>
        <span v-else class="dark:text-soft-silk/60 text-obsidian/70 text-[11px] italic">
            No tools selected
        </span>
    </div>

    <!-- Loader -->
    <div
        v-if="!isError && !isUserMessage && !getTextFromMessage(props.message) && isStreaming"
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
        v-if="
            !isError &&
            (thinkingHtml ||
                (props.message.type === NodeTypeEnum.PARALLELIZATION && !props.isStreaming))
        "
        class="custom_scroll grid h-fit w-full grid-rows-[auto_auto] overflow-x-auto"
        :class="{
            'grid-cols-[10rem_calc(100%-10rem)]': thinkingHtml,
            'grid-cols-[1fr]': props.message.type === NodeTypeEnum.PARALLELIZATION && !thinkingHtml,
        }"
    >
        <UiChatThinkingDisclosure
            v-if="thinkingHtml"
            :thinking-segments="thinkingSegments"
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
        v-if="webSearches.length"
        :web-searches="webSearches"
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
                class="flex max-w-full min-w-0 grow items-center gap-1 overflow-hidden text-sm font-bold"
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
            <span
                v-if="tool.durationMs !== undefined && tool.label !== 'Asked user'"
                :title="formatToolDuration(tool.durationMs)"
                class="border-stone-gray/10 bg-anthracite/30 dark:text-soft-silk/70 text-obsidian/80
                    inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px]
                    font-semibold"
            >
                {{ formatToolDuration(tool.durationMs) }}
            </span>
            <button
                class="hover:bg-stone-gray/10 mb-0.5 ml-1 flex items-center justify-center
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
            data-testid="markdown-renderer-response"
            :class="{
                'hide-code-scrollbar': isStreaming,
                'mt-1': hasAskedUserActivity,
                'mt-4': !hasAskedUserActivity,
            }"
            class="prose prose-invert custom_scroll min-w-full overflow-x-auto
                overflow-y-hidden"
        >
            <MarkdownResponse
                ref="markdownResponseRef"
                :segments="responseSegments"
                :render-mermaid-charts="renderMermaidCharts"
                @open-lightbox="handleOpenLightbox"
                @visualizer-prompt="emit('visualizer-prompt', $event)"
            />
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
                v-for="(text, nodeId) in editZones"
                :key="nodeId"
                class="prose prose-invert bg-obsidian/25 text-soft-silk w-full max-w-none rounded-lg
                    px-2 py-1 whitespace-pre-wrap focus:outline-none"
                contenteditable
                autofocus
                @focus="activeEditNodeId = String(nodeId)"
                @input="handleEditInput(String(nodeId), $event)"
                @keydown.enter.exact.prevent="submitEdit(String(nodeId))"
                @keydown.esc.prevent.stop="emit('cancel-edit')"
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
        :fetched-page-selection="fetchedPageSelection"
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
