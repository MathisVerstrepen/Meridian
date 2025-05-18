<script lang="ts" setup>
const { getOpenRouterModels } = useAPI();

// --- Stores ---
const modelStore = useModelStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { models } = storeToRefs(modelStore);
const { modelsSelectSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { sortModels, triggerFilter } = modelStore;

provideHeadlessUseId(() => useId());

const { data } = await useAsyncData('users', () => getOpenRouterModels());

onMounted(() => {
    models.value = data.value?.data || [];
    sortModels(modelsSelectSettings.value.sortBy);
    triggerFilter();
});
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <NuxtLayout>
            <NuxtPage />
        </NuxtLayout>
    </div>
</template>
