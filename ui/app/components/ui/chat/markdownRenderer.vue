<script setup lang="ts">
import { createApp, h, onBeforeUnmount } from 'vue';
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import type { FileTreeNode, ExtractedIssue } from '@/types/github';
import { useToolCallDetails } from '@/composables/useToolCallDetails';
import type { ToolActivity, ToolCallDetail } from '@/types/toolCall';
import { useMarkdownProcessor } from '~/composables/useMarkdownProcessor';
import GeneratedImageCard from '~/components/ui/chat/utils/generatedImageCard.vue';

const emit = defineEmits(['rendered', 'edit-done', 'triggerScroll']);

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
const mountedImages = shallowRef<
    Map<
        string,
        {
            app: ReturnType<typeof createApp>;
            wrapper: HTMLElement;
        }
    >
>(new Map());

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

const activeImageGenerations = ref<ImageGenState[]>([]);
const toolActivities = ref<ToolActivity[]>([]);
const toolDetail = ref<ToolCallDetail | null>(null);
const isToolDetailOpen = ref(false);
const isToolDetailLoading = ref(false);

const TOOL_ACTIVITY_CONFIG: Array<{
    label: string;
    icon: string;
    pattern: RegExp;
}> = [
    {
        label: 'Generated image',
        icon: 'MdiImageMultipleOutline',
        pattern: /<generating_image(?:\s+id="([^"]+)")?>\s*Prompt:\s*"([^"]*)"\s*<\/generating_image>/g,
    },
    {
        label: 'Image generation error',
        icon: 'PhImageBroken',
        pattern: /<generating_image_error(?:\s+id="([^"]+)")?>([\s\S]*?)<\/generating_image_error>/g,
    },
    {
        label: 'Mermaid diagram',
        icon: 'MaterialSymbolsAccountTreeOutlineRounded',
        pattern: /<generating_mermaid_diagram(?:\s+id="([^"]+)")?>([\s\S]*?)<\/generating_mermaid_diagram>/g,
    },
    {
        label: 'Mermaid generation error',
        icon: 'MaterialSymbolsAccountTreeOutlineRounded',
        pattern: /<generating_mermaid_diagram_error(?:\s+id="([^"]+)")?>([\s\S]*?)<\/generating_mermaid_diagram_error>/g,
    },
];

const extractToolActivities = (markdown: string): ToolActivity[] => {
    const matches: Array<ToolActivity & { index: number }> = [];

    for (const { label, icon, pattern } of TOOL_ACTIVITY_CONFIG) {
        for (const match of markdown.matchAll(pattern)) {
            const toolCallId = match[1];
            const preview = (match[2] || '').trim().replace(/\s+/g, ' ').slice(0, 120);

            if (!toolCallId) {
                continue;
            }

            matches.push({
                index: match.index ?? 0,
                toolCallId,
                label,
                preview,
                icon,
            });
        }
    }

    return matches.sort((a, b) => a.index - b.index).map(({ index, ...tool }) => tool);
};

const stripMermaidToolIndicators = (markdown: string): string => {
    return markdown
        .replace(
            /<generating_mermaid_diagram(?:\s+id="[^"]+")?>[\s\S]*?<\/generating_mermaid_diagram>/g,
            '',
        )
        .replace(
            /<generating_mermaid_diagram_error(?:\s+id="[^"]+")?>[\s\S]*?<\/generating_mermaid_diagram_error>/g,
            '',
        );
};

const processImageGeneration = (markdown: string): string => {
    activeImageGenerations.value = [];
    let processedMarkdown = markdown;

    // 1. Detect Active Generation (Streaming)
    if (markdown.includes('[IMAGE_GEN]') && !markdown.includes('[!IMAGE_GEN]')) {
        const activeGenMatch =
            /<generating_image(?:\s+id="[^"]+")?>\s*Prompt:\s*"([^"]*)"/s;
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

    // 3. Replace Markdown Images with Placeholders
    const markdownImageRegex = /!\[(.*?)\]\((.*?)\)/g;
    processedMarkdown = processedMarkdown.replace(
        markdownImageRegex,
        (_match, altText, imageUrl) => {
            const uuidRegex = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
            const match = imageUrl.match(uuidRegex);
            const fileId = match ? match[0] : '';
            const cleanUrl = `/api/files/view/${fileId}`;

            // Escape attributes to safely store in data-*
            const escapedPrompt = altText.replace(/"/g, '&quot;');

            // Return a placeholder div instead of raw HTML
            return `<div class="generated-image-placeholder" data-prompt="${escapedPrompt}" data-image-url="${cleanUrl}"></div>`;
        },
    );

    return processedMarkdown;
};

// --- Core Logic Functions ---
const parseContent = async (markdown: string) => {
    if (isUserMessage.value) {
        toolActivities.value = [];
        emit('rendered');
        return;
    }

    toolActivities.value = extractToolActivities(markdown);

    const processedMarkdown = processImageGeneration(stripMermaidToolIndicators(markdown));

    await processMarkdown(processedMarkdown, $markedWorker.parse);

    if (!markdown) {
        unmountImageApps();
        if (!props.isStreaming) emit('rendered');
        else nextTick(() => emit('triggerScroll'));
        return;
    }

    if (isError.value && !thinkingHtml.value) {
        showError('Error rendering content. Please try again later.');
    }

    await nextTick();

    enhanceCodeBlocks();
    enhanceGeneratedImages(); // This will now mount the Vue components

    if (responseHtml.value.includes('<pre class="mermaid">')) {
        if (!props.isStreaming) {
            const container = contentRef.value;
            const mermaidBlocks = Array.from(container.querySelectorAll('pre.mermaid'));
            const rawMermaidElements = mermaidBlocks.map((block) => block.innerHTML);

            try {
                await renderMermaidCharts();
            } catch (err) {
                console.error('Mermaid rendering failed:', err);
            }
            enhanceMermaidBlocks(rawMermaidElements);
        }
    }

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

// --- Watchers ---
watch(
    () => props.message,
    (newMessage) => {
        parseContent(getTextFromMessage(newMessage) || '');
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
    unmountImageApps();
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

    <div v-if="toolActivities.length && !isUserMessage && !isError" class="mt-1 flex flex-col">
        <div
            v-for="tool in toolActivities"
            :key="tool.toolCallId"
            :title="tool.preview ? `${tool.label}: ${tool.preview}` : tool.label"
            class="dark:text-soft-silk/80 text-obsidian mb-2 flex h-9 max-w-full items-center
                gap-2 overflow-hidden rounded-lg transition-colors duration-200 ease-in-out"
        >
            <UiIcon :name="tool.icon" class="h-4 w-4 shrink-0" />
            <div class="flex max-w-full min-w-0 items-center gap-1 overflow-hidden text-sm font-bold">
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
                class="hover:bg-stone-gray/10 ml-2 mb-0.5 rounded-md p-1.5 transition-colors duration-200 flex items-center justify-center"
                @click="openToolCallDetail(tool.toolCallId)"
            >
                <UiIcon name="MajesticonsInformationCircleLine" class="h-4 w-4" />
            </button>
        </div>
    </div>

    <!-- Final Assistant Response -->
    <div
        v-if="!isUserMessage && !isError"
        ref="contentRef"
        :class="{
            'hide-code-scrollbar': isStreaming,
        }"
        class="prose prose-invert custom_scroll mt-4 min-w-full overflow-x-auto overflow-y-hidden"
        v-html="responseHtml"
    />

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
