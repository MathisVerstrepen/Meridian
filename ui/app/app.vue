<script lang="ts" setup>
const { getOpenRouterModels, getUserSettings } = useAPI();

const route = useRoute();

// --- Stores ---
const githubStore = useGithubStore();
const modelStore = useModelStore();
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { modelsDropdownSettings, appearanceSettings } = storeToRefs(settingsStore);
const { isReady } = storeToRefs(modelStore);

// --- Actions/Methods from Stores ---
const { checkGitHubStatus } = githubStore;

useHead({
    script: [
        {
            innerHTML: `
				(function() {
					try {
						const theme = localStorage.getItem('theme') || 'standard';
                        const accentColor = localStorage.getItem('accentColor') || '#eb5e28';
						const darkThemes = ['dark', 'oled', 'standard'];
						if (darkThemes.includes(theme)) {
							document.documentElement.classList.add('dark');
						} else {
							document.documentElement.classList.remove('dark');
						}
                        document.documentElement.classList.add('theme-' + theme);
                        document.documentElement.style.setProperty('--color-ember-glow', accentColor);
					} catch (e) {}
				})();
			`,
        },
    ],
    htmlAttrs: {
        class: computed(() => {
            const theme = appearanceSettings.value.theme;
            const themeClass = `theme-${theme}`;
            const darkThemes = ['dark', 'oled', 'standard'];
            return darkThemes.includes(theme) ? themeClass + ' dark' : themeClass;
        }),
    },
});

// --- Actions/Methods from Stores ---
const { setModels, sortModels, triggerFilter } = modelStore;

provideHeadlessUseId(() => useId());

const fetchEssentials = async () => {
    if (route.path.startsWith('/auth/login')) return;
    if (isReady.value) return;

    // Start fetching repositories in the background
    setTimeout(() => {
        checkGitHubStatus().catch((e) => {
            console.error('fetchRepositories background error', e);
        });
    }, 10);

    const [modelList, userSettings] = await Promise.all([getOpenRouterModels(), getUserSettings()]);

    settingsStore.setUserSettings(userSettings);

    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();
};

onMounted(fetchEssentials);

watch(route, fetchEssentials);
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center overflow-hidden">
        <NuxtLayout>
            <NuxtPage />
        </NuxtLayout>

        <UiToastContainer />
    </div>
</template>
