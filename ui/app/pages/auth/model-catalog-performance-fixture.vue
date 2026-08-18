<script setup lang="ts">
import { decodeModelCatalog } from '@/utils/modelCatalog';
import { MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE } from '~~/e2e/fixtures/modelCatalogPerformanceFixture';

definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const summary = shallowRef<Record<string, JsonValue> | null>(null);

onMounted(() => {
    for (let index = 0; index < 10; index += 1) {
        decodeModelCatalog(MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE);
    }

    const durations: number[] = [];
    for (let index = 0; index < 50; index += 1) {
        const startedAt = performance.now();
        decodeModelCatalog(MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE);
        durations.push(performance.now() - startedAt);
    }
    durations.sort((left, right) => left - right);

    summary.value = {
        modelCount: MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE.data.length,
        timing: {
            iterations: durations.length,
            medianMs: durations[Math.floor(durations.length / 2)],
            p95Ms: durations[Math.ceil(durations.length * 0.95) - 1],
        },
    };
});
</script>

<template>
    <main
        data-testid="model-catalog-performance-fixture-page"
        class="bg-obsidian text-soft-silk min-h-screen overflow-auto p-6"
    >
        <h1 class="text-lg font-semibold">Model catalog performance fixture</h1>
        <pre
            v-if="summary"
            data-testid="model-catalog-performance-summary"
            class="mt-4 text-xs"
            >{{ JSON.stringify(summary) }}</pre
        >
        <p v-else data-testid="model-catalog-performance-loading">Loading fixture…</p>
    </main>
</template>
