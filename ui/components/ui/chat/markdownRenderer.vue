<script setup lang="ts">
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import { createApp } from 'vue';
import type { FileTreeNode } from '@/types/github';

const emit = defineEmits(['rendered', 'edit-done', 'triggerScroll']);

const CodeBlockCopyButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/copyButton.vue'),
);
const FullScreenButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/fullScreenButton.vue'),
);

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

// --- Composables ---
const { getTextFromMessage, getFilesFromMessage, getImageUrlsFromMessage } = useMessage();
const { error: showError } = useToast();
const { renderMermaidCharts } = useMermaid();

// --- Local State ---
const thinkingHtml = ref<string>('');
const responseHtml = ref<string>('');
const contentRef = ref<HTMLElement | null>(null);
const error = ref<boolean>(false);

// --- Computed Properties ---
const isUserMessage = computed(() => {
    return props.message.role === MessageRoleEnum.user;
});

// --- Core Logic Functions ---
const parseThinkTag = (markdown: string): string => {
    const fullThinkTagRegex = /\[THINK\]([\s\S]*?)\[!THINK\]/;
    const openThinkTagRegex = /\[THINK\]([\s\S]*)$/;

    const fullTagMatch = fullThinkTagRegex.exec(markdown);
    if (fullTagMatch) {
        thinkingHtml.value = fullTagMatch[1];
        return markdown.replace(fullThinkTagRegex, '');
    }

    const openTagMatch = openThinkTagRegex.exec(markdown);
    if (openTagMatch) {
        thinkingHtml.value = openTagMatch[1];
        return '';
    }

    thinkingHtml.value = '';
    return markdown;
};

const parseErrorTag = (markdown: string): string => {
    const startTag = '[ERROR]';
    const endTag = '[!ERROR]';
    const trimmed = markdown.trim();

    if (trimmed.startsWith(startTag)) {
        const endIndex = trimmed.indexOf(endTag);
        const content =
            endIndex !== -1
                ? trimmed.slice(startTag.length, endIndex)
                : trimmed.slice(startTag.length);
        error.value = true;
        return content.trim();
    }

    if (trimmed.endsWith(endTag)) {
        const startIndex = trimmed.indexOf(startTag);
        const content =
            startIndex !== -1
                ? trimmed.slice(startIndex + startTag.length, trimmed.length - endTag.length)
                : trimmed.slice(0, trimmed.length - endTag.length);
        error.value = true;
        return content.trim();
    }

    return '';
};

const parseContent = async (markdown: string) => {
    error.value = false;

    // User message are shown as raw markdown
    if (isUserMessage.value) {
        emit('rendered');
        return;
    }

    if (!markdown) {
        responseHtml.value = '';
        if (!props.isStreaming) {
            emit('rendered');
        } else {
            nextTick(() => {
                emit('triggerScroll');
            });
        }
        return;
    }

    try {
        const errorMessage = parseErrorTag(markdown);
        if (errorMessage) {
            responseHtml.value = errorMessage;
            emit('rendered');
            return;
        }

        const result = await $markedWorker.parse(markdown);
        const parsedMarkdown = parseThinkTag(result);
        responseHtml.value = parsedMarkdown ?? '';
        nextTick(() => replaceCodeContainers());
    } catch (err) {
        console.error('Markdown parsing error in component:', err);
        showError('Error rendering content. Please try again later.');
        error.value = true;
        responseHtml.value = 'Error rendering content. Please try again later.';
    }

    if (responseHtml.value.includes('<pre class="mermaid">')) {
        await nextTick();
        if (!props.isStreaming) {
            const rawMermaidElement = contentRef.value?.querySelector('pre.mermaid')?.innerHTML;
            try {
                await renderMermaidCharts();
            } catch (err) {
                console.error(err);
            }
            await nextTick();
            replaceMermaidPreTags(rawMermaidElement);
        }
    }

    if (!props.isStreaming) {
        emit('rendered');
    } else {
        nextTick(() => {
            emit('triggerScroll');
        });
    }
};

const replaceMermaidPreTags = (rawMermaidElement: string | undefined) => {
    const container = contentRef.value;
    if (!container) return;

    const mermaidBlocks = Array.from(container.querySelectorAll('pre.mermaid'));
    mermaidBlocks.forEach((block) => {
        const wrapper = document.createElement('div');
        wrapper.classList.add('mermaid-wrapper', 'relative');

        block.parentElement?.insertBefore(wrapper, block);
        wrapper.appendChild(block);

        const mountNode = document.createElement('div');

        const app = createApp(FullScreenButton, {
            renderedElement: block.cloneNode(true),
            rawMermaidElement: rawMermaidElement,
            class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
        });
        app.mount(mountNode);

        wrapper.appendChild(mountNode);
    });
};

const replaceCodeContainers = () => {
    const container = contentRef.value;
    if (!container) return;

    const codeBlocks = Array.from(container.querySelectorAll('pre')).filter((pre) =>
        pre.querySelector('code[class^="language-"]'),
    );

    // for each code block, wrap it in a div and add the buttons
    codeBlocks.forEach((pre: Element) => {
        if (pre.parentElement?.classList.contains('code-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.classList.add('code-wrapper', 'relative');

        pre.parentElement?.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        pre.classList.add('overflow-x-auto', 'rounded-lg', 'custom_scroll', 'bg-[#121212]');
        const mountNode = document.createElement('div');

        const app = createApp(CodeBlockCopyButton, {
            textToCopy: pre.textContent || '',
            class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
        });
        app.mount(mountNode);

        wrapper.appendChild(mountNode);
    });
};

const extractedGithubFiles = ref<FileTreeNode[]>([]);

const replaceGithubFiles = (content: string) => {
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

    return cleaned.trim();
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
    nextTick(() => {
        if (!isUserMessage.value && props.message.content) {
            parseContent(getTextFromMessage(props.message));
        } else {
            emit('rendered');
        }
    });
});
</script>

<template>
    <div
        v-if="error"
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
        <span class="loader relative inline-block h-7 w-7"></span>
        <span
            v-if="props.message.type === NodeTypeEnum.PARALLELIZATION"
            class="text-stone-gray ml-2 text-sm"
        >
            Fetching parallelization data...
        </span>
    </div>

    <!-- For the assistant, parse content -->

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
            :thinkingHtml="thinkingHtml"
            :isStreaming="props.isStreaming"
            @triggerScroll="emit('triggerScroll')"
        ></UiChatThinkingDisclosure>

        <UiChatParallelizationDisclosure
            v-if="props.message.type === NodeTypeEnum.PARALLELIZATION"
            :data="props.message.data"
            :nodeType="props.message.type"
            :isStreaming="props.isStreaming"
        >
        </UiChatParallelizationDisclosure>
    </div>

    <!-- Final Assistant Response -->
    <div
        v-if="!isUserMessage && !error"
        :class="{
            'hide-code-scrollbar': isStreaming,
        }"
        class="prose prose-invert custom_scroll min-w-full overflow-x-auto"
        v-html="responseHtml"
        ref="contentRef"
    ></div>

    <!-- For the user, just show the original content and associated files -->
    <div v-else-if="!error">
        <!-- Files -->
        <div class="mb-1 flex w-fit flex-col gap-2 whitespace-pre-wrap">
            <UiChatAttachmentImages
                :images="getImageUrlsFromMessage(props.message)"
            ></UiChatAttachmentImages>
            <UiChatAttachmentFiles
                :files="getFilesFromMessage(props.message)"
            ></UiChatAttachmentFiles>
        </div>

        <!-- Message -->
        <!-- EDIT MODE -->
        <div
            v-if="editMode"
            class="prose prose-invert bg-obsidian/10 text-soft-silk w-full max-w-none rounded-lg px-2 py-1
                whitespace-pre-wrap focus:outline-none"
            contenteditable
            autofocus
            @keydown.enter.exact.prevent="
                emit('edit-done', ($event.target as HTMLElement).innerText)
            "
        >
            {{ getTextFromMessage(props.message) }}
        </div>
        <!-- NORMAL MODE -->
        <div v-else class="prose prose-invert text-soft-silk max-w-none whitespace-pre-wrap">
            {{ replaceGithubFiles(getTextFromMessage(props.message)) }}
            <UiChatGithubFileChatInlineGroup
                :extractedGithubFiles="extractedGithubFiles"
            ></UiChatGithubFileChatInlineGroup>
        </div>
    </div>

    <!-- Edit Mode -->
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
