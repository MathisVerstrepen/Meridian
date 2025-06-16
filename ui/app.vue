<script lang="ts" setup>
const { getOpenRouterModels, getUserSettings } = useAPI();

const route = useRoute();

// --- Stores ---
const modelStore = useModelStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);
const { isReady } = storeToRefs(modelStore);

// --- Actions/Methods from Stores ---
const { setModels, sortModels, triggerFilter } = modelStore;

provideHeadlessUseId(() => useId());

const fetchEssentials = async () => {
    if (route.path.startsWith('/auth/login')) return;
    if (isReady.value) return;

    const [modelList, userSettings] = await Promise.all([getOpenRouterModels(), getUserSettings()]);

    globalSettingsStore.setUserSettings(userSettings);

    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();
};

onMounted(fetchEssentials);

watch(route, fetchEssentials);
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <NuxtLayout>
            <NuxtPage />
        </NuxtLayout>
    </div>
</template>
