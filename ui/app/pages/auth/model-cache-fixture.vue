<script setup lang="ts">
definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const { models } = storeToRefs(useModelStore());
</script>

<template>
    <main data-testid="model-cache-fixture-page">
        <span v-for="model in models" :key="model.id" data-testid="model-cache-entry">
            {{ model.name }}
        </span>
    </main>
</template>
