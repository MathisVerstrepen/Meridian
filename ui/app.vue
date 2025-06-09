<script lang="ts" setup>
const { getOpenRouterModels, getUserSettings } = useAPI();

// --- Stores ---
const modelStore = useModelStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { models } = storeToRefs(modelStore);
const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { sortModels, triggerFilter } = modelStore;

provideHeadlessUseId(() => useId());

const { data: modelList } = await useAsyncData('models', () => getOpenRouterModels());
const { data: userSettings } = await useAsyncData('userSettings', () => getUserSettings());

onMounted(() => {
    models.value = modelList.value?.data || [];
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();

    globalSettingsStore.setUserSettings(userSettings.value);
});
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <NuxtLayout>
            <NuxtPage />
        </NuxtLayout>
    </div>
</template>
