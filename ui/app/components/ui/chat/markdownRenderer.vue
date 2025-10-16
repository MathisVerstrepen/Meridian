<script setup lang="ts">
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import type { FileTreeNode } from '@/types/github';
import { useMarkdownProcessor } from '~/composables/useMarkdownProcessor';

const emit = defineEmits(['rendered', 'edit-done', 'triggerScroll']);

// --- Props ---
const props = withDefaults(
    defineProps<{
        message: Message;
        editMode: boolean;
        isStreaming?: boolean;
    }>(),
    {
        isStreaming: false,
    },
);

// --- Plugins ---
const { $markedWorker } = useNuxtApp();

// --- Local State ---
const contentRef = ref<HTMLElement | null>(null);

// --- Composables ---
const { getTextFromMessage, getFilesFromMessage, getImageUrlsFromMessage } = useMessage();
const { error: showError } = useToast();
const { renderMermaidCharts } = useMermaid();
const {
    thinkingHtml,
    responseHtml,
    isError,
    processMarkdown,
    enhanceMermaidBlocks,
    enhanceCodeBlocks,
} = useMarkdownProcessor(contentRef as Ref<HTMLElement | null>);

// --- Computed ---
const isUserMessage = computed(() => {
    return props.message.role === MessageRoleEnum.user;
});

// --- Core Logic Functions ---
const parseContent = async (markdown: string) => {
    // User messages are handled separately and don't use the markdown processor.
    if (isUserMessage.value) {
        emit('rendered');
        return;
    }

    // Handle empty content.
    if (!markdown) {
        responseHtml.value = '';
        thinkingHtml.value = '';
        if (!props.isStreaming) {
            emit('rendered');
        } else {
            nextTick(() => emit('triggerScroll'));
        }
        return;
    }

    // Use the composable to process the markdown into reactive HTML strings.
    await processMarkdown(markdown, $markedWorker.parse);

    if (isError.value && !thinkingHtml.value) {
        showError('Error rendering content. Please try again later.');
    }

    // Wait for Vue to render the v-html content.
    await nextTick();

    // Enhance the newly rendered DOM elements.
    enhanceCodeBlocks();

    if (responseHtml.value.includes('<pre class="mermaid">')) {
        // Add wrappers and buttons BEFORE Mermaid converts the <pre> to an <svg>.
        enhanceMermaidBlocks();
        if (!props.isStreaming) {
            try {
                await renderMermaidCharts();
            } catch (err) {
                console.error('Mermaid rendering failed:', err);
            }
        }
    }

    // Notify parent component that rendering is complete or scroll needs adjustment.
    if (!props.isStreaming) {
        emit('rendered');
    } else {
        nextTick(() => emit('triggerScroll'));
    }
};

// --- Logic for User Messages ---
const extractedGithubFiles = ref<FileTreeNode[]>([]);

const parseUserText = (content: string) => {
    // 1. Extract github files
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
            } as FileTreeNode;

            extractedGithubFiles.value.push(file);
            return '';
        },
    );

    // 2. Remove node IDs tags
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
        class="custom_scroll grid h-fit w-full grid-rows-[3rem_auto] overflow-x-auto"
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

    <!-- Final Assistant Response -->
    <div
        v-if="!isUserMessage && !isError"
        ref="contentRef"
        :class="{
            'hide-code-scrollbar': isStreaming,
        }"
        class="prose prose-invert custom_scroll min-w-full overflow-x-auto overflow-y-hidden"
        v-html="responseHtml"
    />

    <!-- For the user, just show the original content and associated files -->
    <div v-else-if="!isError">
        <!-- Files -->
        <div class="mb-1 flex w-fit flex-col gap-2 whitespace-pre-wrap">
            <UiChatAttachmentImages :images="getImageUrlsFromMessage(props.message)" />
            <UiChatAttachmentFiles :files="getFilesFromMessage(props.message)" />
        </div>

        <!-- Message -->
        <!-- EDIT MODE -->
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

        <!-- NORMAL MODE -->
        <div v-else class="prose prose-invert text-soft-silk max-w-none whitespace-pre-wrap">
            {{ parseUserText(getTextFromMessage(props.message)) }}
            <UiChatGithubFileChatInlineGroup :extracted-github-files="extractedGithubFiles" />
        </div>
    </div>
</template>

<style scoped>
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
