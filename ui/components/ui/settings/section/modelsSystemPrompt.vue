<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div>
        <div v-for="systemPrompt in modelsSettings.systemPrompt" :key="systemPrompt.name">
            <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-gray-100">
                {{ systemPrompt.name }}
            </h3>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {{ systemPrompt.prompt }}
            </p>
            <div class="mt-4">
                <hr class="border-t border-gray-200 dark:border-gray-700" />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
