<script lang="ts" setup>
import {
    UiSettingsSectionGeneral,
    UiSettingsSectionModels,
    UiSettingsSectionModelsDropdown,
    UiSettingsSectionAppearance,
    UiSettingsSectionAccount,
    UiSettingsSectionBlocks,
    UiSettingsSectionBlocksParallelization,
    UiSettingsSectionBlocksRouting,
    UiSettingsSectionBlocksGithub,
} from '#components';

const route = useRoute();
const router = useRouter();

// --- Page Meta ---
definePageMeta({ middleware: 'auth' });

// --- Stores ---
const settingsStore = useSettingsStore();

// --- Actions/Methods from Stores ---
const { triggerSettingsUpdate } = settingsStore;

// --- State from Stores ---
const { hasChanged } = storeToRefs(settingsStore);

// --- Composables ---
const { getUserSettings } = useAPI();

enum TabNames {
    GENERAL = 'general',
    ACCOUNT = 'account',
    APPEARANCE = 'appearance',
    MODELS = 'models',
    MODELS_DROPDOWN = 'dropdown',
    BLOCKS = 'blocks',
    BLOCKS_PARALLELIZATION = 'parallelization',
    BLOCKS_ROUTING = 'routing',
    BLOCKS_GITHUB = 'github',
}

interface ITab {
    name: string;
    group: string;
    component: Component;
    icon: string;
    subTabs?: ITab[];
}

const Tabs = {
    GENERAL: {
        name: TabNames.GENERAL,
        group: TabNames.GENERAL,
        icon: 'MaterialSymbolsSettingsRounded',
        component: markRaw(UiSettingsSectionGeneral),
        subTabs: [],
    } as ITab,
    ACCOUNT: {
        name: TabNames.ACCOUNT,
        group: TabNames.ACCOUNT,
        icon: 'MaterialSymbolsAccountCircle',
        component: markRaw(UiSettingsSectionAccount),
        subTabs: [],
    } as ITab,
    APPEARANCE: {
        name: TabNames.APPEARANCE,
        group: TabNames.APPEARANCE,
        icon: 'MaterialSymbolsPaletteOutline',
        component: markRaw(UiSettingsSectionAppearance),
        subTabs: [],
    } as ITab,
    MODELS: {
        name: TabNames.MODELS,
        group: TabNames.MODELS,
        icon: 'RiBrain2Line',
        component: markRaw(UiSettingsSectionModels),
        subTabs: [
            {
                name: TabNames.MODELS_DROPDOWN,
                group: TabNames.MODELS,
                icon: 'BxCaretDownSquare',
                component: markRaw(UiSettingsSectionModelsDropdown),
            },
        ],
    } as ITab,
    BLOCKS: {
        name: TabNames.BLOCKS,
        group: TabNames.BLOCKS,
        icon: 'ClarityBlockSolid',
        component: markRaw(UiSettingsSectionBlocks),
        subTabs: [
            {
                name: TabNames.BLOCKS_PARALLELIZATION,
                group: TabNames.BLOCKS,
                icon: 'HugeiconsDistributeHorizontalCenter',
                component: markRaw(UiSettingsSectionBlocksParallelization),
            },
            {
                name: TabNames.BLOCKS_ROUTING,
                group: TabNames.BLOCKS,
                icon: 'MaterialSymbolsAltRouteRounded',
                component: markRaw(UiSettingsSectionBlocksRouting),
            },
            {
                name: TabNames.BLOCKS_GITHUB,
                group: TabNames.BLOCKS,
                icon: 'MdiGithub',
                component: markRaw(UiSettingsSectionBlocksGithub),
            },
        ],
    } as ITab,
} as const;

// --- Local State ---
const query = route.query.tab as string;

const findTabByName = (name: string): ITab | undefined => {
    if (!name) return undefined;
    for (const tab of Object.values(Tabs)) {
        if (tab.name === name) return tab;
        if (tab.subTabs) {
            const subTab = tab.subTabs.find((st) => st.name === name);
            if (subTab) return subTab;
        }
    }
    return undefined;
};

const selectedTab = ref<ITab>(findTabByName(query) || Tabs.GENERAL);

// --- Methods ---
const backToLastPage = async () => {
    if (hasChanged.value) {
        const confirmLeave = confirm('You have unsaved changes. Are you sure you want to leave?');
        if (!confirmLeave) return;
        const userSettings = await getUserSettings();
        settingsStore.setUserSettings(userSettings);
    }
    const preOauthUrl = sessionStorage.getItem('preOauthUrl');
    if (preOauthUrl) {
        sessionStorage.removeItem('preOauthUrl');
        router.push(preOauthUrl);
    } else {
        history.back();
    }
};

// --- Watchers ---
watch(selectedTab, (newTab) => {
    document.title = 'Settings - ' + newTab.name.charAt(0).toUpperCase() + newTab.name.slice(1);
    history.replaceState({}, '', window.location.pathname + '?tab=' + newTab.name);
});
</script>

<template>
    <div
        class="grid h-full w-full max-w-[1700px] grid-rows-[5rem_calc(100%-5rem)] items-start px-20 py-20"
    >
        <div class="flex h-20 w-full items-center justify-between">
            <h1 class="text-stone-gray text-3xl font-bold">Settings</h1>
            <button
                class="hover:bg-stone-gray/10 flex h-10 w-10 items-center justify-center justify-self-end rounded-full p-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                @click="backToLastPage"
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>
        </div>
        <div
            class="bg-anthracite/75 border-stone-gray/10 grid h-0 min-h-full max-w-full min-w-0 grid-cols-[20%_80%]
                rounded-2xl border-2 px-5 py-10 shadow-lg"
        >
            <div
                class="border-stone-gray/10 flex h-0 min-h-full w-full flex-col justify-between border-r-2 px-5"
            >
                <ul>
                    <li v-for="tab in Object.values(Tabs)" :key="tab.name" class="mb-2">
                        <button
                            :class="{
                                'bg-stone-gray/10 text-stone-gray': selectedTab.name === tab.name,
                                'text-stone-gray/50 hover:bg-stone-gray/10 hover:text-stone-gray':
                                    selectedTab.name !== tab.name,
                            }"
                            class="flex h-12 w-full items-center justify-start gap-2 rounded-lg px-4 font-bold capitalize
                                transition-colors duration-200 ease-in-out"
                            @click="selectedTab = tab"
                        >
                            <UiIcon :name="tab.icon" class="h-5 w-5" />
                            <span>{{ tab.name }}</span>
                        </button>
                        <ul
                            v-if="tab.subTabs"
                            v-show="selectedTab.group === tab.group"
                            class="mt-2 ml-4"
                        >
                            <li v-for="subTab in tab.subTabs" :key="subTab.name" class="mb-2">
                                <button
                                    :class="{
                                        'bg-stone-gray/10 text-stone-gray':
                                            selectedTab.name === subTab.name,
                                        'text-stone-gray/50 hover:bg-stone-gray/10 hover:text-stone-gray':
                                            selectedTab.name !== subTab.name,
                                    }"
                                    class="flex h-12 w-full items-center justify-start gap-2 rounded-lg px-4 font-bold capitalize
                                        transition-colors duration-200 ease-in-out"
                                    @click="selectedTab = subTab"
                                >
                                    <UiIcon :name="subTab.icon" class="h-5 w-5" />
                                    {{ subTab.name }}
                                </button>
                            </li>
                        </ul>
                    </li>
                </ul>

                <button
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline dark:text-soft-silk text-obsidian
                        w-full rounded-lg px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                        focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="!hasChanged"
                    @click="triggerSettingsUpdate"
                >
                    Save
                </button>
            </div>

            <UiSettingsSectionLayout>
                <template #header>
                    <UiIcon :name="selectedTab.icon" class="text-stone-gray h-8 w-8" />
                    <p>{{ selectedTab.name }}</p>
                </template>
                <template #default>
                    <Transition
                        name="fade"
                        mode="out-in"
                        enter-active-class="transition duration-200 ease-out"
                        enter-from-class="transform opacity-0"
                        enter-to-class="transform opacity-100"
                        leave-active-class="transition duration-150 ease-in"
                        leave-from-class="transform opacity-100"
                        leave-to-class="transform opacity-0"
                    >
                        <component :is="selectedTab.component" :key="selectedTab.name" />
                    </Transition>
                </template>
            </UiSettingsSectionLayout>
        </div>
    </div>
</template>

<style scoped></style>
