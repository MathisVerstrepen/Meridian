<script setup lang="ts">
import type { Message } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';
const emit = defineEmits(['rendered', 'edit-done']);
import { createApp } from 'vue';

const CodeBlockButton = defineAsyncComponent(
    () => import('@/components/ui/chat/codeBlockButton.vue'),
);

// --- Plugins ---
const { $marked } = useNuxtApp();

// --- Local State ---
const thinkingHtml = ref<string>('');
const responseHtml = ref<string>('');
const contentRef = ref<HTMLElement | null>(null);
const error = ref<boolean>(false);

// --- Props ---
const props = withDefaults(
    defineProps<{
        message: Message;
        disableHighlight?: boolean;
        editMode: boolean;
        isStreaming?: boolean;
    }>(),
    {
        isStreaming: false,
    },
);

// --- Core Logic Functions ---
const parseThinkTag = (markdown: string) => {
    const fullThinkTagRegex = /\[THINK\]([\s\S]*?)\[!THINK\]/;
    const openThinkTagRegex = /\[THINK\]([\s\S]*)$/;

    const fullTagMatch = markdown.match(fullThinkTagRegex);
    if (fullTagMatch) {
        thinkingHtml.value = fullTagMatch[1];
        return markdown.replace(fullThinkTagRegex, '');
    }

    // Only [THINK] found, without [!THINK]
    const openTagMatch = markdown.match(openThinkTagRegex);
    if (openTagMatch) {
        thinkingHtml.value = openTagMatch[1];
        return '';
    }

    return markdown;
};

const parseContent = async (markdown: string) => {
    error.value = false;

    if (!markdown) {
        responseHtml.value = '';
        return;
    }

    try {
        const result = await $marked.parse(markdown);
        const parsedMarkdown = parseThinkTag(result);
        responseHtml.value = parsedMarkdown ?? '';
        nextTick(() => replaceCodeContainers());
    } catch (err) {
        console.error('Markdown parsing error in component:', err);
        error.value = true;
        responseHtml.value = `<pre class="text-red-500">Error rendering content.</pre>`;
    } finally {
        emit('rendered');
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

        const app = createApp(CodeBlockButton, {
            codeContent: pre.textContent || '',
            rawCode: pre.textContent || '',
        });
        app.mount(mountNode);

        wrapper.appendChild(mountNode);
    });
}

// --- Watchers ---
watch(
    () => props.message.content,
    (newContent) => {
        parseContent(newContent);
    },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    nextTick(() => {
        if (!props.disableHighlight && props.message.content) {
            parseContent(props.message.content);
        }
    });
});
</script>

<template>
    <!-- Loader -->
    <div class="flex h-7 items-center" v-if="!props.disableHighlight && !props.message.content">
        <span class="loader relative inline-block h-7 w-7"></span>
        <span
            class="text-stone-gray ml-2 text-sm"
            v-if="props.message.type === NodeTypeEnum.PARALLELIZATION"
        >
            Fetching parallelization data...
        </span>
    </div>

    <!-- For the assistant, parse content -->

    <!-- Thinking response -->
    <div
        class="grid h-fit w-full grid-rows-[3rem_auto]"
        :class="{
            'grid-cols-[10rem_calc(100%-10rem)]': thinkingHtml,
            'grid-cols-[1fr]': props.message.type === NodeTypeEnum.PARALLELIZATION && !thinkingHtml,
        }"
        v-if="
            thinkingHtml ||
            (props.message.type === NodeTypeEnum.PARALLELIZATION && !props.isStreaming)
        "
    >
        <UiChatThinkingDisclosure
            v-if="thinkingHtml"
            :thinkingHtml="thinkingHtml"
            :nodeType="props.message.type"
        ></UiChatThinkingDisclosure>

        <UiChatParallelizationDisclosure
            v-if="props.message.type === NodeTypeEnum.PARALLELIZATION"
            :data="props.message.data"
            :nodeType="props.message.type"
            :isStreaming="props.isStreaming"
        >
        </UiChatParallelizationDisclosure>
    </div>

    <!-- Final Response -->
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none"
        v-html="responseHtml"
        v-if="!disableHighlight"
        ref="contentRef"
    ></div>

    <!-- For the user, just show the original content -->
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none whitespace-pre-wrap"
        v-else-if="!editMode"
    >
        {{ props.message.content }}
    </div>

    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert bg-obsidian/10 w-full max-w-none rounded-lg px-2 py-1 whitespace-pre-wrap
            focus:outline-none"
        contenteditable
        autofocus
        @keydown.enter.exact.prevent="emit('edit-done', ($event.target as HTMLElement).innerText)"
        v-else
    >
        {{ props.message.content }}
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
