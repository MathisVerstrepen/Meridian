<script setup lang="ts">
const emit = defineEmits(['rendered', 'edit-done']);

// --- Plugins ---
const { $marked } = useNuxtApp();

// --- Local State ---
const thinkingHtml = ref<string>('');
const responseHtml = ref<string>('');

const error = ref<boolean>(false);

// --- Props ---
const props = defineProps<{
    content: string;
    disableHighlight?: boolean;
    isStreaming?: boolean;
    editMode: boolean;
}>();

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
    } catch (err) {
        console.error('Markdown parsing error in component:', err);
        error.value = true;
        responseHtml.value = `<pre class="text-red-500">Error rendering content.</pre>`;
    } finally {
        emit('rendered');
    }
};

// --- Watchers ---
watch(
    () => props.content,
    (newContent) => {
        parseContent(newContent);
    },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    nextTick(() => {
        if (!props.disableHighlight && props.content) {
            parseContent(props.content);
        }
    });
});
</script>

<template>
    <span
        class="loader relative inline-block h-7 w-7"
        v-if="!props.disableHighlight && !props.content"
    ></span>

    <!-- For the assistant, parse content -->

    <!-- Thinking response -->
    <HeadlessDisclosure as="div" v-if="thinkingHtml" class="mt-2 mb-4 max-w-none" v-slot="{ open }">
        <HeadlessDisclosureButton
            class="bg-anthracite mb-2 flex items-center gap-2 rounded-lg px-4 py-2"
            :class="{
                'animate-pulse': isStreaming,
            }"
        >
            <UiIcon name="RiBrain2Line" class="text-soft-silk/80 h-4 w-4" />
            <span class="text-soft-silk/80 text-sm font-bold">Thoughts</span>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="text-soft-silk/80 h-4 w-4 transition-transform duration-200"
                :class="open ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>
        <HeadlessDisclosurePanel as="div" class="flex h-full w-full items-stretch gap-4">
            <div class="bg-anthracite w-1 shrink-0 rounded"></div>
            <div
                class="prose prose-invert h-full w-full max-w-none pr-5 opacity-75"
                v-html="thinkingHtml"
            ></div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>

    <!-- Final Response -->
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none"
        v-html="responseHtml"
        v-if="!disableHighlight"
    ></div>

    <!-- For the user, just show the original content -->
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none whitespace-pre-wrap"
        v-else-if="!editMode"
    >
        {{ props.content }}
    </div>

    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert bg-obsidian/10 w-full max-w-none rounded-lg px-2 py-1 whitespace-pre-wrap
            focus:outline-none"
        contenteditable
        autofocus
        @keydown.enter.exact.prevent="emit('edit-done', $event)"
        v-else
    >
        {{ props.content }}
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
