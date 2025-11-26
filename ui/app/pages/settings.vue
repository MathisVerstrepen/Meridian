<script lang="ts" setup>
import {
    UiSettingsSectionGeneral,
    UiSettingsSectionModels,
    UiSettingsSectionModelsDropdown,
    UiSettingsSectionModelsSystemPrompt,
    UiSettingsSectionAppearance,
    UiSettingsSectionAccount,
    UiSettingsSectionBlocks,
    UiSettingsSectionBlocksAttachment,
    UiSettingsSectionBlocksParallelization,
    UiSettingsSectionBlocksRouting,
    UiSettingsSectionBlocksGithub,
    UiSettingsSectionBlocksContextMerger,
    UiSettingsSectionTools,
    UiSettingsSectionToolsWebSearch,
    UiSettingsSectionToolsLinkExtraction,
    UiSettingsSectionToolsImageGen,
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
    MODELS_SYSTEM_PROMPT = 'system prompt',
    BLOCKS = 'blocks',
    BLOCKS_ATTACHMENT = 'attachment',
    BLOCKS_PARALLELIZATION = 'parallelization',
    BLOCKS_ROUTING = 'routing',
    BLOCKS_GITHUB = 'github',
    BLOCKS_CONTEXT_MERGER = 'context merger',
    TOOLS = 'tools',
    TOOLS_WEB_SEARCH = 'web search',
    TOOLS_LINK_EXTRACTION = 'link extraction',
    TOOLS_IMAGE_GENERATION = 'image generation',
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
            {
                name: TabNames.MODELS_SYSTEM_PROMPT,
                group: TabNames.MODELS,
                icon: 'MaterialSymbolsEditNoteOutlineRounded',
                component: markRaw(UiSettingsSectionModelsSystemPrompt),
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
                name: TabNames.BLOCKS_ATTACHMENT,
                group: TabNames.BLOCKS,
                icon: 'MajesticonsAttachment',
                component: markRaw(UiSettingsSectionBlocksAttachment),
            },
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
            {
                name: TabNames.BLOCKS_CONTEXT_MERGER,
                group: TabNames.BLOCKS,
                icon: 'TablerArrowMerge',
                component: markRaw(UiSettingsSectionBlocksContextMerger),
            },
        ],
    } as ITab,
    TOOLS: {
        name: TabNames.TOOLS,
        group: TabNames.TOOLS,
        icon: 'MdiWrenchOutline',
        component: markRaw(UiSettingsSectionTools),
        subTabs: [
            {
                name: TabNames.TOOLS_WEB_SEARCH,
                group: TabNames.TOOLS,
                icon: 'MdiWeb',
                component: markRaw(UiSettingsSectionToolsWebSearch),
            },
            {
                name: TabNames.TOOLS_LINK_EXTRACTION,
                group: TabNames.TOOLS,
                icon: 'MdiLinkVariant',
                component: markRaw(UiSettingsSectionToolsLinkExtraction),
            },
            {
                name: TabNames.TOOLS_IMAGE_GENERATION,
                group: TabNames.TOOLS,
                icon: 'MdiImageMultipleOutline',
                component: markRaw(UiSettingsSectionToolsImageGen),
            }
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
        if (history.back === undefined || history.back === null || history.length <= 2) {
            router.push('/');
            return;
        }
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
    <div class="relative flex h-full w-full items-center justify-center overflow-hidden">
        <UiSettingsUtilsBlobBackground />

        <div
            class="z-10 grid h-full w-full max-w-[1700px] grid-rows-[auto_1fr] items-start gap-y-8
                px-8 py-12 md:px-12 lg:px-16"
        >
            <div class="flex h-12 w-full items-center justify-between">
                <h1 class="text-stone-gray text-3xl font-bold">Settings</h1>
                <button
                    class="hover:bg-stone-gray/10 flex h-10 w-10 items-center justify-center
                        justify-self-end rounded-full p-1 transition-colors duration-200 ease-in-out
                        hover:cursor-pointer"
                    @click="backToLastPage"
                >
                    <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
                </button>
            </div>
            <div
                class="bg-anthracite/25 border-stone-gray/10 grid h-0 min-h-full max-w-full min-w-0
                    grid-cols-[280px_1fr] rounded-2xl border-2 shadow-lg backdrop-blur-lg"
            >
                <div
                    class="border-stone-gray/10 flex h-0 min-h-full w-full flex-col justify-between
                        border-r-2 p-4"
                >
                    <nav class="custom_scroll flex flex-col gap-4 overflow-y-auto">
                        <div v-for="tab in Object.values(Tabs)" :key="tab.name">
                            <button
                                :class="[
                                    `flex h-11 w-full items-center justify-start gap-3 rounded-lg
                                    px-3 font-semibold capitalize transition-colors duration-200
                                    ease-in-out`,
                                    {
                                        'bg-ember-glow/10 text-ember-glow':
                                            selectedTab.name === tab.name && !tab.subTabs?.length,
                                        'text-ember-glow':
                                            selectedTab.group === tab.group &&
                                            (selectedTab.name !== tab.name || tab.subTabs?.length),
                                        [`text-stone-gray/60 hover:bg-stone-gray/10
                                        hover:text-soft-silk`]: selectedTab.group !== tab.group,
                                    },
                                ]"
                                @click="selectedTab = tab"
                            >
                                <UiIcon :name="tab.icon" class="h-5 w-5" />
                                <span>{{ tab.name }}</span>
                            </button>
                            <ul
                                v-if="tab.subTabs?.length"
                                class="border-stone-gray/10 mt-2 ml-4 flex flex-col gap-1 border-l-2
                                    pl-5"
                            >
                                <li v-for="subTab in tab.subTabs" :key="subTab.name">
                                    <button
                                        :class="[
                                            `flex h-10 w-full items-center justify-start gap-3
                                            rounded-md px-3 text-sm font-semibold capitalize
                                            transition-colors duration-200 ease-in-out`,
                                            {
                                                'bg-ember-glow/10 text-ember-glow':
                                                    selectedTab.name === subTab.name,
                                                [`text-stone-gray/60 hover:bg-stone-gray/10
                                                hover:text-soft-silk`]:
                                                    selectedTab.name !== subTab.name,
                                            },
                                        ]"
                                        @click="selectedTab = subTab"
                                    >
                                        <UiIcon :name="subTab.icon" class="h-5 w-5" />
                                        <span>{{ subTab.name }}</span>
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </nav>

                    <button
                        class="bg-ember-glow hover:bg-ember-glow/80 focus:shadow-outline
                            text-soft-silk mt-4 w-full rounded-lg px-4 py-2.5 text-sm font-bold
                            duration-200 ease-in-out hover:cursor-pointer focus:outline-none
                            disabled:cursor-not-allowed disabled:opacity-50"
                        :disabled="!hasChanged"
                        @click="triggerSettingsUpdate"
                    >
                        Save Changes
                    </button>
                </div>

                <UiSettingsSectionLayout>
                    <template #header>
                        <UiIcon :name="selectedTab.icon" class="h-7 w-7" />
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
    </div>
</template>

<style scoped></style>
