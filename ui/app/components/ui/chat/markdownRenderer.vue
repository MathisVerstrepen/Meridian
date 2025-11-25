<script setup lang="ts">
import { createApp, h, onBeforeUnmount } from 'vue';
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import type { FileTreeNode } from '@/types/github';
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
const mountedImageApps = ref<{ unmount: () => void }[]>([]);

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

const processImageGeneration = (markdown: string): string => {
    activeImageGenerations.value = [];
    let processedMarkdown = markdown;

    // 1. Detect Active Generation (Streaming)
    if (markdown.includes('[IMAGE_GEN]') && !markdown.includes('[!IMAGE_GEN]')) {
        const activeGenMatch = /<generating_image>\s*Prompt:\s*"([^"]*)"/s;
        const match = markdown.match(activeGenMatch);

        activeImageGenerations.value.push({
            prompt: match?.[1] || 'Creating your image...',
            isGenerating: true,
        });
    }

    console.log('Processed Markdown before replacements:', activeImageGenerations.value);

    // 2. Clean up Helper Tags
    processedMarkdown = processedMarkdown
        .replace(/\[IMAGE_GEN\]/g, '')
        .replace(/\[!IMAGE_GEN\]/g, '')
        .replace(/<generating_image>[\s\S]*?<\/generating_image>/g, '');

    // 3. Replace Markdown Images with Placeholders
    const markdownImageRegex = /!\[(.*?)\]\((.*?)\)/g;
    processedMarkdown = processedMarkdown.replace(
        markdownImageRegex,
        (_match, altText, imageUrl) => {
            const cleanUrl = imageUrl.split(' ')[0].trim();

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
        emit('rendered');
        return;
    }

    // Unmount any previously mounted image components to prevent memory leaks on re-render
    unmountImageApps();

    const processedMarkdown = processImageGeneration(markdown);

    await processMarkdown(processedMarkdown, $markedWorker.parse);

    if (!markdown) {
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

    placeholders.forEach((el) => {
        const { prompt, imageUrl } = el.dataset;
        if (!prompt || !imageUrl) return;

        // Create a Vue app instance for each placeholder
        const app = createApp({
            render: () =>
                h(GeneratedImageCard, {
                    prompt,
                    imageUrl,
                    onOpenLightbox: handleOpenLightbox,
                }),
        });

        // Mount the component onto the placeholder element
        app.mount(el);

        // Keep track of the app instance for later cleanup
        mountedImageApps.value.push(app);
    });
};

const unmountImageApps = () => {
    mountedImageApps.value.forEach((app) => app.unmount());
    mountedImageApps.value = [];
};

const closeLightbox = () => {
    lightboxImage.value = null;
};

// --- Logic for User Messages ---
const extractedGithubFiles = ref<FileTreeNode[]>([]);

const parseUserText = (content: string) => {
    extractedGithubFiles.value = [];
    const extractRegex = /--- Start of file: (.+?) ---([\s\S]*?)--- End of file: \1 ---/g;
    const cleaned = content.replace(
        extractRegex,
        (_match, filename: string, fileContent: string) => {
            const file = {
                name: filename.trim().split('/').pop() || '',
                path: filename.trim(),
                type: 'file',
                content: fileContent.trim(),
                children: [],
            } as FileTreeNode;

            extractedGithubFiles.value.push(file);
            return '';
        },
    );

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
    <UiChatUtilsWebSearch v-for="search in webSearches" :key="search.query" :web-search="search" />

    <!-- Fetched Page Content -->
    <UiChatUtilsFetchedPage v-if="fetchedPages.length" :fetched-pages="fetchedPages" />

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
            <UiChatGithubFileChatInlineGroup :extracted-github-files="extractedGithubFiles" />
        </div>
    </div>

    <!-- Image Generation Loaders -->
    <UiChatUtilsGeneratedImageLoader :active-image-generations="activeImageGenerations" />

    <!-- Lightbox Modal -->
    <UiChatUtilsGeneratedImageLightbox
        :lightbox-image="lightboxImage"
        @close-lightbox="closeLightbox"
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
