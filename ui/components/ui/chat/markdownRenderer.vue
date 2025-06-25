<script setup lang="ts">
import type { Message } from '@/types/graph';
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';
import { createApp } from 'vue';

const emit = defineEmits(['rendered', 'edit-done', 'triggerScroll']);

const CodeBlockCopyButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/copyButton.vue'),
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
function parseThinkTag(markdown: string): string {
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
}

const parseContent = async (markdown: string) => {
    error.value = false;

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
        const result = await $markedWorker.parse(markdown);
        const parsedMarkdown = parseThinkTag(result);
        responseHtml.value = parsedMarkdown ?? '';
        nextTick(() => replaceCodeContainers());
    } catch (err) {
        console.error('Markdown parsing error in component:', err);
        showError('Error rendering content. Please try again later.');
        error.value = true;
        responseHtml.value = `<pre class="text-red-500">Error rendering content.</pre>`;
    } finally {
        if (!props.isStreaming) {
            emit('rendered');
        } else {
            nextTick(() => {
                emit('triggerScroll');
            });
        }
    }
};

function replaceCodeContainers() {
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

        pre.classList.add('overflow-x-auto', 'rounded-lg');
        const mountNode = document.createElement('div');

        const app = createApp(CodeBlockCopyButton, {
            textToCopy: pre.textContent || '',
            class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
        });
        app.mount(mountNode);

        wrapper.appendChild(mountNode);
    });
}

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
        class="grid h-fit w-full grid-rows-[3rem_auto] overflow-x-auto"
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
        v-if="!isUserMessage"
        :class="{
            'text-red-500': error,
            'hide-code-scrollbar': isStreaming,
        }"
        class="prose prose-invert min-w-full overflow-x-auto"
        v-html="responseHtml"
        ref="contentRef"
    ></div>

    <!-- For the user, just show the original content and associated files -->
    <div v-else>
        <!-- Files -->
        <div
            :class="{ 'text-red-500': error }"
            class="mb-1 flex w-fit flex-col gap-2 whitespace-pre-wrap"
        >
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
            class="prose prose-invert bg-obsidian/10 w-full max-w-none rounded-lg px-2 py-1 whitespace-pre-wrap
                focus:outline-none"
            :class="{ 'text-red-500': error }"
            contenteditable
            autofocus
            @keydown.enter.exact.prevent="
                emit('edit-done', ($event.target as HTMLElement).innerText)
            "
        >
            {{ getTextFromMessage(props.message) }}
        </div>
        <!-- NORMAL MODE -->
        <div
            v-else
            :class="{ 'text-red-500': error }"
            class="prose prose-invert max-w-none whitespace-pre-wrap"
        >
            {{ getTextFromMessage(props.message) }}
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
