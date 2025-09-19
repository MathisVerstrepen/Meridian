<script setup lang="ts">
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import { createApp } from 'vue';
import { useMarkdownRenderer } from '@/composables/useMarkdownRenderer';

const emit = defineEmits(['rendered', 'edit-done', 'triggerScroll']);

// --- Async Components for DOM enhancement ---
const CodeBlockCopyButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/copyButton.vue'),
);
const FullScreenButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/fullScreenButton.vue'),
);
const WebSearchBlock = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/webSearch.vue'),
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

// --- Composables ---
const { getTextFromMessage, getFilesFromMessage, getImageUrlsFromMessage } = useMessage();
const {
    thinkingHtml,
    responseHtml,
    error,
    extractedGithubFiles,
    extractedWebSearches,
    processAssistantMessage,
    parseUserText,
    getEditZones,
} = useMarkdownRenderer();

// --- Local State ---
const thinkingResponseRef = ref<HTMLElement | null>(null);
const finalResponseRef = ref<HTMLElement | null>(null);

// --- Computed Properties ---
const isUserMessage = computed(() => props.message.role === MessageRoleEnum.user);

// --- DOM Enhancement ---
/**
 * Injects a fullscreen button into rendered Mermaid diagram containers.
 */
const enhanceMermaidDiagrams = () => {
    const container = finalResponseRef.value;
    if (!container) return;

    const mermaidBlocks = Array.from(container.querySelectorAll('pre.mermaid'));
    mermaidBlocks.forEach((block) => {
        if (block.parentElement?.classList.contains('mermaid-wrapper')) return;

        const rawMermaidElement = block.innerHTML;
        const wrapper = document.createElement('div');
        wrapper.classList.add('mermaid-wrapper', 'relative');

        block.parentElement?.insertBefore(wrapper, block);
        wrapper.appendChild(block);

        const mountNode = document.createElement('div');
        mountNode.classList.add('absolute', 'top-2', 'right-2');

        const app = createApp(FullScreenButton, {
            renderedElement: block.cloneNode(true),
            rawMermaidElement,
            class: 'hover:bg-stone-gray/20 bg-stone-gray/10 h-8 w-8 p-1 backdrop-blur-sm',
        });
        app.mount(mountNode);

        wrapper.appendChild(mountNode);
    });
};

/**
 * Injects a copy button into rendered code block containers.
 */
const enhanceCodeBlocks = () => {
    const container = finalResponseRef.value;
    if (!container) return;

    const codeBlocks = Array.from(container.querySelectorAll('pre')).filter((pre) =>
        (pre.firstChild?.firstChild as Element)?.classList.contains('replace-code-containers'),
    );

    codeBlocks.forEach((pre: Element) => {
        if (pre.parentElement?.classList.contains('code-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.classList.add('code-wrapper', 'relative');

        pre.parentElement?.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);

        pre.classList.add('overflow-x-auto', 'rounded-lg', 'custom_scroll', 'bg-[#121212]');

        const mountNode = document.createElement('div');
        mountNode.classList.add('absolute', 'top-2', 'right-2');

        const app = createApp(CodeBlockCopyButton, {
            textToCopy: pre.textContent || '',
            class: 'hover:bg-stone-gray/20 bg-stone-gray/10 h-8 w-8 p-1 backdrop-blur-sm',
        });
        app.mount(mountNode);

        wrapper.appendChild(mountNode);
    });
};

const enhanceWebSearchBlocks = () => {
    const containerFinal = finalResponseRef.value;
    const containerThinking = thinkingResponseRef.value;

    const finalWebSearchDivs = Array.from(
        containerFinal?.querySelectorAll('div.web-search') || []
    ) as Element[];
    
    const thinkingWebSearchDivs = Array.from(
        containerThinking?.querySelectorAll('div.web-search') || []
    ) as Element[];

    const allWebSearchDivs = finalWebSearchDivs.concat(thinkingWebSearchDivs);

    allWebSearchDivs.forEach((div, index) => {
        const webSearchData = extractedWebSearches.value[index];
        if (!webSearchData) return;

        const parent = div.parentElement;
        if (!parent) return;

        const app = createApp(WebSearchBlock, { webSearch: webSearchData });
        const mountNode = document.createElement('div');
        
        // If the div is in thinking container, teleport to start of final container
        if (thinkingWebSearchDivs.includes(div) && containerFinal) {
            containerFinal.insertBefore(mountNode, containerFinal.firstChild as Node | null);
        } else {
            parent.replaceChild(mountNode, div);
        }
        
        // Remove the original div if it was in thinking container
        if (thinkingWebSearchDivs.includes(div)) {
            div.remove();
        }
        
        app.mount(mountNode);
    });
};

// --- Main Parsing Orchestration ---
const parseMessageContent = async (message: Message) => {
    if (isUserMessage.value) {
        emit('rendered');
        return;
    }

    const markdown = getTextFromMessage(message) || '';
    const { hasMermaid } = await processAssistantMessage(markdown);

    await nextTick();
    enhanceCodeBlocks();
    enhanceWebSearchBlocks();
    if (hasMermaid && !props.isStreaming) {
        enhanceMermaidDiagrams();
    }

    if (!props.isStreaming) {
        emit('rendered');
    } else {
        emit('triggerScroll');
    }
};

// --- Watchers & Lifecycle ---
watch(() => props.message, parseMessageContent, { deep: true });

onMounted(() => {
    // Initial render on component mount
    nextTick(() => {
        if (props.message.content) {
            parseMessageContent(props.message);
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
        <span class="loader relative inline-block h-7 w-7" />
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
        ref="thinkingResponseRef"
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
        v-if="!isUserMessage && !error"
        ref="finalResponseRef"
        :class="{
            'hide-code-scrollbar': isStreaming,
        }"
        class="prose prose-invert custom_scroll min-w-full overflow-x-auto overflow-y-hidden"
        v-html="responseHtml"
    />

    <!-- For the user, just show the original content and associated files -->
    <div v-else-if="!error">
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
                class="prose prose-invert bg-obsidian/25 text-soft-silk w-full max-w-none rounded-lg px-2 py-1
                    whitespace-pre-wrap focus:outline-none"
                contenteditable
                autofocus
                @keydown.enter.exact.prevent="
                    emit('edit-done', nodeId, ($event.target as HTMLElement).innerText)
                "
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
