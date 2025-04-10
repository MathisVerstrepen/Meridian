<script setup lang="ts">
const emit = defineEmits(['rendered']);

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
        renderedHtml.value = `<pre class="text-red-500">Error rendering content.</pre>`;
    } finally {
        console.log('Markdown parsing completed');
        emit('rendered');
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
    <div
        :class="{ 'text-red-500': error }"
        class="prose prose-invert max-w-none"
        v-html="renderedHtml"
    ></div>
</template>

<style scoped></style>
