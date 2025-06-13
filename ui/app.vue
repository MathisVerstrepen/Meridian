<script lang="ts" setup>
const { getOpenRouterModels, getUserSettings } = useAPI();

const route = useRoute();

// --- Stores ---
const modelStore = useModelStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { setModels, sortModels, triggerFilter } = modelStore;

provideHeadlessUseId(() => useId());

onMounted(async () => {
    if (route.path.startsWith('/auth/login')) return;

    const [modelList, userSettings] = await Promise.all([getOpenRouterModels(), getUserSettings()]);

    globalSettingsStore.setUserSettings(userSettings);

    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
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
