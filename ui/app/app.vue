<script lang="ts" setup>
const { getAvailableModels, getUserSettings } = useAPI();
const { refreshInferenceProviderStatuses } = useInferenceProviderStatuses();

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
                        if (theme === 'custom') {
                            try {
                                const colors = JSON.parse(localStorage.getItem('customThemeColors') || '{}');
                                if (colors.softSilk) document.documentElement.style.setProperty('--color-soft-silk', colors.softSilk);
                                if (colors.stoneGray) document.documentElement.style.setProperty('--color-stone-gray', colors.stoneGray);
                                if (colors.anthracite) document.documentElement.style.setProperty('--color-anthracite', colors.anthracite);
                                if (colors.obsidian) document.documentElement.style.setProperty('--color-obsidian', colors.obsidian);
                            } catch (e) {}
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
            const darkThemes = ['dark', 'oled', 'standard', 'custom'];
            return darkThemes.includes(theme) ? themeClass + ' dark' : themeClass;
        }),
    },
});

// --- Actions/Methods from Stores ---
const { setModels, showModelDiscoveryWarnings, sortModels, triggerFilter } = modelStore;

provideHeadlessUseId(() => useId());

// Apply custom theme colors reactively when the user edits them
watch(
    () => appearanceSettings.value.customThemeColors,
    (colors) => {
        if (!import.meta.client || !colors) return;
        if (appearanceSettings.value.theme !== 'custom') return;
        document.documentElement.style.setProperty('--color-soft-silk', colors.softSilk);
        document.documentElement.style.setProperty('--color-stone-gray', colors.stoneGray);
        document.documentElement.style.setProperty('--color-anthracite', colors.anthracite);
        document.documentElement.style.setProperty('--color-obsidian', colors.obsidian);
    },
    { deep: true, immediate: true },
);

// Apply/remove custom theme colors when theme switches to/from custom
watch(
    () => appearanceSettings.value.theme,
    (theme) => {
        if (!import.meta.client) return;
        if (theme === 'custom') {
            const colors = appearanceSettings.value.customThemeColors;
            document.documentElement.style.setProperty('--color-soft-silk', colors.softSilk);
            document.documentElement.style.setProperty('--color-stone-gray', colors.stoneGray);
            document.documentElement.style.setProperty('--color-anthracite', colors.anthracite);
            document.documentElement.style.setProperty('--color-obsidian', colors.obsidian);
        } else {
            document.documentElement.style.removeProperty('--color-soft-silk');
            document.documentElement.style.removeProperty('--color-stone-gray');
            document.documentElement.style.removeProperty('--color-anthracite');
            document.documentElement.style.removeProperty('--color-obsidian');
        }
    },
);

const fetchEssentials = async () => {
    if (
        route.path.startsWith('/auth/login') ||
        route.path.startsWith('/auth/markdown-renderer-fixture')
    ) {
        return;
    }
    if (isReady.value) return;

    // Start fetching repositories in the background
    setTimeout(() => {
        checkGitHubStatus().catch((e) => {
            console.error('fetchRepositories background error', e);
        });
    }, 10);

    const modelListPromise = getAvailableModels();
    const providerStatusesPromise = refreshInferenceProviderStatuses();
    const userSettings = await getUserSettings();

    settingsStore.setUserSettings(userSettings);

    const [modelList] = await Promise.all([modelListPromise, providerStatusesPromise]);

    setModels(modelList.data);
    showModelDiscoveryWarnings(modelList.warnings ?? []);
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

        <ClientOnly>
            <UiLibraryPromptEditor />
            <UiLibraryPromptImprover />
        </ClientOnly>
    </div>
</template>
