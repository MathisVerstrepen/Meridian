<script setup lang="ts">
const emit = defineEmits(['rendered']);

// --- Plugins ---
const { $marked } = useNuxtApp();

// --- Local State ---
const renderedHtml = ref<string>('');
const error = ref<boolean>(false);

// --- Props ---
const props = defineProps<{
    content: string;
    disableHighlight?: boolean;
}>();

// --- Core Logic Functions ---
const parseContent = async (markdown: string) => {
    error.value = false;

    if (!markdown) {
        renderedHtml.value = '';
        return;
    }

    try {
        const result = await $marked.parse(markdown);
        renderedHtml.value = result ?? '';
    } catch (err) {
        console.error('Markdown parsing error in component:', err);
        error.value = true;
        renderedHtml.value = `<pre class="text-red-500">Error rendering content.</pre>`;
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
        if (!props.disableHighlight) {
            parseContent(props.content);
        }
    });
});
</script>

<template>
    <!-- For the assistant, parse content -->
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none"
        v-html="renderedHtml"
        v-if="!disableHighlight"
    ></div>

    <!-- For the user, just show the original content -->
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none whitespace-pre-wrap"
        v-else
    >
        {{ props.content }}
    </div>
</template>

<style scoped></style>
