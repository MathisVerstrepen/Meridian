<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';

const props = defineProps<{
    content: string;
}>();

const { $marked } = useNuxtApp();
const renderedHtml = ref<string>('');
const error = ref<boolean>(false);

const parseContent = async (markdown: string) => {
    if (!markdown) {
        renderedHtml.value = '';
        error.value = false;
        return;
    }

    error.value = false;
    try {
        const result = await $marked.parse(markdown);
        renderedHtml.value = result ?? '';
    } catch (err) {
        console.error('Markdown parsing error in component:', err);
        error.value = true;
        renderedHtml.value = `<pre>Error rendering content.</pre>`;
    }
};

onMounted(() => {
    parseContent(props.content);
});

watch(
    () => props.content,
    (newContent) => {
        parseContent(newContent);
    },
);
</script>

<template>
    <div v-if="error" class="text-red-500">Error rendering markdown.</div>
    <div v-else class="prose prose-invert max-w-none" v-html="renderedHtml"></div>
</template>

<style scoped></style>
