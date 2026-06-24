<script lang="ts" setup>
import {
    UiSettingsSectionModelsDropdown,
    UiSettingsSectionModelsSystemPrompt,
    UiSettingsSectionAppearance,
    UiSettingsSectionAccountProfile,
    UiSettingsSectionAccountSecurity,
    UiSettingsSectionAccountApiKeys,
    UiSettingsSectionAccountProviders,
    UiSettingsSectionAccountUsage,
    UiSettingsSectionBlocks,
    UiSettingsSectionBlocksPromptImprover,
    UiSettingsSectionBlocksParallelization,
    UiSettingsSectionBlocksRouting,
    UiSettingsSectionBlocksContextMerger,
    UiSettingsSectionBlocksPromptTemplates,
    UiSettingsSectionFilesUploads,
    UiSettingsSectionFilesDocumentProcessing,
    UiSettingsSectionGeneralCanvasStartup,
    UiSettingsSectionGeneralChatDisplay,
    UiSettingsSectionModelsDefault,
    UiSettingsSectionModelsGenerationParameters,
    UiSettingsSectionModelsReasoning,
    UiSettingsSectionRepositoryConnections,
    UiSettingsSectionRepositoryBehavior,
    UiSettingsSectionTools,
    UiSettingsSectionToolsWebSearch,
    UiSettingsSectionToolsLinkExtraction,
    UiSettingsSectionToolsImageGen,
    UiSettingsSectionToolsVisualise,
    UiSettingsSectionAdminUsers,
} from '#components';
import type { User } from '@/types/user';

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
const { user } = useUserSession();

const isAdmin = computed(() => (user.value as User)?.is_admin ?? false);

enum TabNames {
    PROFILE = 'Profile',
    SECURITY = 'Security',
    API_KEYS = 'API Keys',
    USAGE_LIMITS = 'Usage & Limits',
    ADMIN = 'Admin',
    THEME = 'Theme',
    CANVAS_STARTUP = 'Canvas Startup',
    CHAT_DISPLAY = 'Chat Display',
    MODEL_PICKER = 'Model Picker',
    INFERENCE_PROVIDERS = 'Inference Providers',
    DEFAULT_MODELS = 'Default Models',
    GENERATION_PARAMETERS = 'Generation Parameters',
    REASONING = 'Reasoning',
    GLOBAL_SYSTEM_PROMPTS = 'Global System Prompts',
    CONTEXT_WHEEL = 'Context Wheel',
    PROMPT_IMPROVER = 'Prompt Improver',
    PROMPT_TEMPLATES = 'Prompt Templates',
    ROUTING = 'Routing',
    PARALLELIZATION = 'Parallelization',
    CONTEXT_MERGER = 'Context Merger',
    UPLOADS_FILE_MANAGER = 'Uploads & File Manager',
    DOCUMENT_PROCESSING = 'Document Processing',
    REPOSITORY_CONNECTIONS = 'Repository Connections',
    REPOSITORY_BEHAVIOR = 'Repository Behavior',
    TOOL_DEFAULTS = 'Tool Defaults',
    WEB_SEARCH = 'Web Search',
    LINK_EXTRACTION = 'Link Extraction',
    IMAGE_VIDEO_GENERATION = 'Image & Video Generation',
    VISUALISE = 'Visualise',
}

enum GroupNames {
    ACCOUNT = 'Account',
    APPEARANCE_INTERFACE = 'Appearance & Interface',
    AI_PROVIDERS_MODELS = 'AI Providers & Models',
    WORKFLOW_NODES = 'Workflow & Nodes',
    FILES_REPOSITORIES = 'Files & Repositories',
    TOOLS = 'Tools',
}

interface ITab {
    name: string;
    group: string;
    component: Component;
    icon: string;
}

interface ISettingsGroup {
    name: GroupNames;
    icon: string;
    tabs: ITab[];
}

const createTab = (
    group: GroupNames,
    name: TabNames,
    icon: string,
    component: Component,
): ITab => ({
    name,
    group,
    icon,
    component: markRaw(component),
});

const tabAliases: Record<string, TabNames> = {
    account: TabNames.PROFILE,
    providers: TabNames.INFERENCE_PROVIDERS,
    usage: TabNames.USAGE_LIMITS,
    general: TabNames.CANVAS_STARTUP,
    appearance: TabNames.THEME,
    models: TabNames.DEFAULT_MODELS,
    dropdown: TabNames.MODEL_PICKER,
    'system prompt': TabNames.GLOBAL_SYSTEM_PROMPTS,
    blocks: TabNames.CONTEXT_WHEEL,
    attachment: TabNames.UPLOADS_FILE_MANAGER,
    github: TabNames.REPOSITORY_CONNECTIONS,
    tools: TabNames.TOOL_DEFAULTS,
    'image generation': TabNames.IMAGE_VIDEO_GENERATION,
    'user management': TabNames.ADMIN,
};

const tabSearchTerms: Partial<Record<TabNames, string[]>> = {
    [TabNames.PROFILE]: ['avatar', 'username', 'email', 'plan badge', 'log out', 'delete account'],
    [TabNames.SECURITY]: ['change password', 'password'],
    [TabNames.API_KEYS]: ['openrouter', 'api key'],
    [TabNames.USAGE_LIMITS]: ['web search usage', 'link extraction usage', 'storage usage'],
    [TabNames.ADMIN]: ['user management', 'delete users', 'plan', 'provider', 'verified', 'joined'],
    [TabNames.THEME]: ['application theme', 'accent color'],
    [TabNames.CANVAS_STARTUP]: ['open chat view', 'canvas creation', 'default node type'],
    [TabNames.CHAT_DISPLAY]: ['thinking panels', 'thinking in context', 'message collapsing'],
    [TabNames.MODEL_PICKER]: [
        'sort models',
        'dropdown section order',
        'hide free',
        'hide paid',
        'pinned models',
    ],
    [TabNames.INFERENCE_PROVIDERS]: [
        'claude agent',
        'github copilot',
        'z.ai',
        'gemini cli',
        'codex',
        'opencode',
    ],
    [TabNames.DEFAULT_MODELS]: ['chat model', 'routing model', 'title generation', 'tool selection'],
    [TabNames.GENERATION_PARAMETERS]: ['max tokens', 'temperature', 'top p', 'top k', 'penalty'],
    [TabNames.REASONING]: ['exclude reasoning', 'reasoning effort'],
    [TabNames.GLOBAL_SYSTEM_PROMPTS]: ['system prompt', 'enable', 'disable', 'edit', 'reorder'],
    [TabNames.CONTEXT_WHEEL]: ['wheel slots', 'main block', 'linked options'],
    [TabNames.PROMPT_IMPROVER]: ['override prompt improver model', 'prompt improver model'],
    [TabNames.PROMPT_TEMPLATES]: ['template library', 'marketplace', 'create', 'edit', 'delete'],
    [TabNames.ROUTING]: ['route groups', 'default route group', 'route rules', 'route models'],
    [TabNames.PARALLELIZATION]: ['parallel models', 'aggregator model', 'aggregator prompt'],
    [TabNames.CONTEXT_MERGER]: ['merger mode', 'last n', 'summarizer model', 'include user messages'],
    [TabNames.UPLOADS_FILE_MANAGER]: ['upload folder', 'default sort', 'default view', 'remember sort'],
    [TabNames.DOCUMENT_PROCESSING]: ['pdf engine'],
    [TabNames.REPOSITORY_CONNECTIONS]: ['github app', 'gitlab'],
    [TabNames.REPOSITORY_BEHAVIOR]: ['auto pull'],
    [TabNames.TOOL_DEFAULTS]: ['auto tool selection', 'selected tools'],
    [TabNames.WEB_SEARCH]: [
        'number of results',
        'google search api key',
        'sites to ignore',
        'sites to prefer',
    ],
    [TabNames.LINK_EXTRACTION]: ['max content length'],
    [TabNames.IMAGE_VIDEO_GENERATION]: ['default image model', 'default video model'],
    [TabNames.VISUALISE]: ['mermaid', 'svg', 'html', 'retry', 'standard model', 'expert model'],
};

const groups = computed<ISettingsGroup[]>(() => {
    const accountTabs = [
        createTab(
            GroupNames.ACCOUNT,
            TabNames.PROFILE,
            'MaterialSymbolsAccountCircle',
            UiSettingsSectionAccountProfile,
        ),
        createTab(
            GroupNames.ACCOUNT,
            TabNames.SECURITY,
            'MaterialSymbolsLockOutline',
            UiSettingsSectionAccountSecurity,
        ),
        createTab(
            GroupNames.ACCOUNT,
            TabNames.API_KEYS,
            'MaterialSymbolsKeyRounded',
            UiSettingsSectionAccountApiKeys,
        ),
        createTab(
            GroupNames.ACCOUNT,
            TabNames.USAGE_LIMITS,
            'MaterialSymbolsBarChartRounded',
            UiSettingsSectionAccountUsage,
        ),
    ];

    if (isAdmin.value) {
        accountTabs.push(
            createTab(
                GroupNames.ACCOUNT,
                TabNames.ADMIN,
                'MaterialSymbolsLightAdminPanelSettingsOutline',
                UiSettingsSectionAdminUsers,
            ),
        );
    }

    return [
        {
            name: GroupNames.ACCOUNT,
            icon: 'MaterialSymbolsAccountCircle',
            tabs: accountTabs,
        },
        {
            name: GroupNames.APPEARANCE_INTERFACE,
            icon: 'MaterialSymbolsPaletteOutline',
            tabs: [
                createTab(
                    GroupNames.APPEARANCE_INTERFACE,
                    TabNames.THEME,
                    'MaterialSymbolsPaletteOutline',
                    UiSettingsSectionAppearance,
                ),
                createTab(
                    GroupNames.APPEARANCE_INTERFACE,
                    TabNames.CANVAS_STARTUP,
                    'MaterialSymbolsAddToQueueOutlineRounded',
                    UiSettingsSectionGeneralCanvasStartup,
                ),
                createTab(
                    GroupNames.APPEARANCE_INTERFACE,
                    TabNames.CHAT_DISPLAY,
                    'MaterialSymbolsChatBubbleOutlineRounded',
                    UiSettingsSectionGeneralChatDisplay,
                ),
                createTab(
                    GroupNames.APPEARANCE_INTERFACE,
                    TabNames.MODEL_PICKER,
                    'BxCaretDownSquare',
                    UiSettingsSectionModelsDropdown,
                ),
            ],
        },
        {
            name: GroupNames.AI_PROVIDERS_MODELS,
            icon: 'RiBrain2Line',
            tabs: [
                createTab(
                    GroupNames.AI_PROVIDERS_MODELS,
                    TabNames.INFERENCE_PROVIDERS,
                    'MaterialSymbolsElectricBoltRounded',
                    UiSettingsSectionAccountProviders,
                ),
                createTab(
                    GroupNames.AI_PROVIDERS_MODELS,
                    TabNames.DEFAULT_MODELS,
                    'RiBrain2Line',
                    UiSettingsSectionModelsDefault,
                ),
                createTab(
                    GroupNames.AI_PROVIDERS_MODELS,
                    TabNames.GENERATION_PARAMETERS,
                    'MaterialSymbolsTuneRounded',
                    UiSettingsSectionModelsGenerationParameters,
                ),
                createTab(
                    GroupNames.AI_PROVIDERS_MODELS,
                    TabNames.REASONING,
                    'MaterialSymbolsPsychologyOutlineRounded',
                    UiSettingsSectionModelsReasoning,
                ),
                createTab(
                    GroupNames.AI_PROVIDERS_MODELS,
                    TabNames.GLOBAL_SYSTEM_PROMPTS,
                    'MaterialSymbolsEditNoteOutlineRounded',
                    UiSettingsSectionModelsSystemPrompt,
                ),
            ],
        },
        {
            name: GroupNames.WORKFLOW_NODES,
            icon: 'ClarityBlockSolid',
            tabs: [
                createTab(
                    GroupNames.WORKFLOW_NODES,
                    TabNames.CONTEXT_WHEEL,
                    'MaterialSymbolsRadioButtonChecked',
                    UiSettingsSectionBlocks,
                ),
                createTab(
                    GroupNames.WORKFLOW_NODES,
                    TabNames.PROMPT_IMPROVER,
                    'MynauiSparklesSolid',
                    UiSettingsSectionBlocksPromptImprover,
                ),
                createTab(
                    GroupNames.WORKFLOW_NODES,
                    TabNames.PROMPT_TEMPLATES,
                    'MaterialSymbolsTextSnippetOutlineRounded',
                    UiSettingsSectionBlocksPromptTemplates,
                ),
                createTab(
                    GroupNames.WORKFLOW_NODES,
                    TabNames.ROUTING,
                    'MaterialSymbolsAltRouteRounded',
                    UiSettingsSectionBlocksRouting,
                ),
                createTab(
                    GroupNames.WORKFLOW_NODES,
                    TabNames.PARALLELIZATION,
                    'HugeiconsDistributeHorizontalCenter',
                    UiSettingsSectionBlocksParallelization,
                ),
                createTab(
                    GroupNames.WORKFLOW_NODES,
                    TabNames.CONTEXT_MERGER,
                    'TablerArrowMerge',
                    UiSettingsSectionBlocksContextMerger,
                ),
            ],
        },
        {
            name: GroupNames.FILES_REPOSITORIES,
            icon: 'MajesticonsAttachment',
            tabs: [
                createTab(
                    GroupNames.FILES_REPOSITORIES,
                    TabNames.UPLOADS_FILE_MANAGER,
                    'MajesticonsAttachment',
                    UiSettingsSectionFilesUploads,
                ),
                createTab(
                    GroupNames.FILES_REPOSITORIES,
                    TabNames.DOCUMENT_PROCESSING,
                    'MaterialSymbolsPictureAsPdfRounded',
                    UiSettingsSectionFilesDocumentProcessing,
                ),
                createTab(
                    GroupNames.FILES_REPOSITORIES,
                    TabNames.REPOSITORY_CONNECTIONS,
                    'MdiGithub',
                    UiSettingsSectionRepositoryConnections,
                ),
                createTab(
                    GroupNames.FILES_REPOSITORIES,
                    TabNames.REPOSITORY_BEHAVIOR,
                    'MaterialSymbolsSyncRounded',
                    UiSettingsSectionRepositoryBehavior,
                ),
            ],
        },
        {
            name: GroupNames.TOOLS,
            icon: 'MdiWrenchOutline',
            tabs: [
                createTab(
                    GroupNames.TOOLS,
                    TabNames.TOOL_DEFAULTS,
                    'MdiWrenchOutline',
                    UiSettingsSectionTools,
                ),
                createTab(
                    GroupNames.TOOLS,
                    TabNames.WEB_SEARCH,
                    'MdiWeb',
                    UiSettingsSectionToolsWebSearch,
                ),
                createTab(
                    GroupNames.TOOLS,
                    TabNames.LINK_EXTRACTION,
                    'MdiLinkVariant',
                    UiSettingsSectionToolsLinkExtraction,
                ),
                createTab(
                    GroupNames.TOOLS,
                    TabNames.IMAGE_VIDEO_GENERATION,
                    'MdiImageMultipleOutline',
                    UiSettingsSectionToolsImageGen,
                ),
                createTab(
                    GroupNames.TOOLS,
                    TabNames.VISUALISE,
                    'MaterialSymbolsBarChartRounded',
                    UiSettingsSectionToolsVisualise,
                ),
            ],
        },
    ];
});

const allTabs = computed(() => groups.value.flatMap((group) => group.tabs));

// --- Local State ---
const query = route.query.tab as string;
const settingsSearch = ref('');

const findTabByName = (name: string): ITab | undefined => {
    if (!name) return undefined;
    const normalizedName = name.toLowerCase();
    const alias = tabAliases[normalizedName];
    const resolvedName = alias ?? name;
    const directMatch = allTabs.value.find((tab) => tab.name === resolvedName);

    if (directMatch) return directMatch;

    const groupMatch = groups.value.find((group) => group.name.toLowerCase() === normalizedName);
    if (groupMatch) {
        return groupMatch.tabs[0];
    }

    return undefined;
};

const selectedTab = ref<ITab | null>(findTabByName(query) || null);

const filteredGroups = computed<ISettingsGroup[]>(() => {
    const search = settingsSearch.value.trim().toLowerCase();

    if (!search) {
        return groups.value;
    }

    return groups.value
        .map((group) => {
            const groupMatches = group.name.toLowerCase().includes(search);
            const tabs = groupMatches
                ? group.tabs
                : group.tabs.filter((tab) => {
                      const haystack = [
                          tab.name,
                          tab.group,
                          ...(tabSearchTerms[tab.name as TabNames] ?? []),
                      ]
                          .join(' ')
                          .toLowerCase();
                      return haystack.includes(search);
                  });

            return {
                ...group,
                tabs,
            };
        })
        .filter((group) => group.tabs.length > 0);
});

const hasSearchResults = computed(() => filteredGroups.value.length > 0);

const selectGroup = (group: ISettingsGroup) => {
    const [firstGroupTab] = group.tabs;
    if (firstGroupTab) {
        selectedTab.value = firstGroupTab;
    }
};

const selectTab = (tab: ITab) => {
    selectedTab.value = tab;
};

const showHub = () => {
    selectedTab.value = null;
    settingsSearch.value = '';
};

const openFirstSearchResult = () => {
    const firstGroup = filteredGroups.value[0];
    const firstResult = firstGroup?.tabs[0];

    if (firstResult) {
        selectTab(firstResult);
    }
};

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
    if (!newTab) {
        document.title = 'Settings';
        history.replaceState({}, '', window.location.pathname);
        return;
    }

    document.title = 'Settings - ' + newTab.name.charAt(0).toUpperCase() + newTab.name.slice(1);
    history.replaceState(
        {},
        '',
        window.location.pathname + '?tab=' + encodeURIComponent(newTab.name),
    );
});
</script>

<template>
    <div class="relative flex h-full w-full items-center justify-center overflow-hidden">
        <UiSettingsUtilsBlobBackground />

        <div
            class="z-10 flex h-full w-full max-w-[1700px] flex-col gap-y-5 px-8 py-8
                md:px-12 lg:px-14"
        >
            <div class="flex h-12 w-full shrink-0 items-center justify-between">
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
                v-if="!selectedTab"
                class="flex min-h-0 max-w-full min-w-0 flex-1 flex-col overflow-hidden"
            >
                <div class="shrink-0 pt-2 pb-16">
                    <div
                        class="border-stone-gray/15 focus-within:border-ember-glow/60 bg-stone-gray/5
                            mx-auto flex h-12 max-w-2xl items-center gap-3 rounded-xl border px-4
                            transition-colors duration-200"
                    >
                        <UiIcon
                            name="MdiMagnify"
                            class="text-stone-gray/50 focus-within:text-ember-glow h-5 w-5 shrink-0
                                transition-colors duration-200"
                        />
                        <input
                            v-model="settingsSearch"
                            type="search"
                            placeholder="Search settings..."
                            class="text-soft-silk placeholder:text-stone-gray/45 h-full w-full
                                bg-transparent text-base font-medium outline-none"
                            @keydown.enter.prevent="openFirstSearchResult"
                        />
                    </div>
                </div>

                <div class="hide-scrollbar min-h-0 flex-1 overflow-y-auto">
                    <div
                        v-if="hasSearchResults"
                        class="mx-auto grid max-w-6xl gap-x-10 gap-y-8 md:grid-cols-2 xl:grid-cols-3"
                    >
                        <section
                            v-for="group in filteredGroups"
                            :key="group.name"
                            class="group/card flex min-w-0 flex-col"
                        >
                            <button
                                class="flex w-full cursor-pointer items-center gap-3 border-b border-stone-gray/10
                                    pb-3 text-left transition-colors duration-200"
                                @click="selectGroup(group)"
                            >
                                <span
                                    class="text-stone-gray group-hover/card:text-ember-glow flex h-9 w-9
                                        shrink-0 items-center justify-center rounded-lg
                                        transition-colors duration-200"
                                >
                                    <UiIcon :name="group.icon" class="h-6 w-6" />
                                </span>
                                <span class="min-w-0 flex-1">
                                    <span
                                        class="text-soft-silk group-hover/card:text-ember-glow block text-lg
                                            leading-tight font-bold transition-colors duration-200"
                                    >
                                        {{ group.name }}
                                    </span>
                                    <span class="text-stone-gray/50 mt-0.5 block text-xs">
                                        {{ group.tabs.length }}
                                        {{ group.tabs.length === 1 ? 'section' : 'sections' }}
                                    </span>
                                </span>
                            </button>

                            <ul class="mt-2 flex flex-col">
                                <li v-for="tab in group.tabs" :key="tab.name">
                                    <button
                                        class="text-stone-gray/80 hover:bg-stone-gray/8 hover:text-soft-silk
                                            group/item flex w-full cursor-pointer items-center gap-3 rounded-lg
                                            px-3 py-2 text-left text-sm font-medium transition-colors
                                            duration-200"
                                        @click="selectTab(tab)"
                                    >
                                        <UiIcon
                                            :name="tab.icon"
                                            class="text-stone-gray/50 group-hover/item:text-ember-glow h-4
                                                w-4 shrink-0 transition-colors duration-200"
                                        />
                                        <span class="min-w-0 truncate">{{ tab.name }}</span>
                                    </button>
                                </li>
                            </ul>
                        </section>
                    </div>

                    <div
                        v-else
                        class="mx-auto mt-4 flex w-full max-w-xl flex-col items-center px-8 py-12
                            text-center"
                    >
                        <UiIcon name="MaterialSymbolsSearchOff" class="text-stone-gray/40 h-12 w-12" />
                        <h2 class="text-soft-silk mt-3 text-xl font-bold">No settings found</h2>
                        <p class="text-stone-gray/70 mt-2 text-sm">
                            Try searching for a category, subcategory, or setting name.
                        </p>
                        <button
                            class="text-ember-glow hover:text-ember-glow/80 mt-4 cursor-pointer text-sm
                                font-bold"
                            @click="settingsSearch = ''"
                        >
                            Clear search
                        </button>
                    </div>
                </div>
            </div>

            <div
                v-else
                class="bg-anthracite/25 border-stone-gray/10 grid min-h-0 max-w-full min-w-0 flex-1
                    grid-cols-[280px_1fr] rounded-2xl border-2 shadow-lg backdrop-blur-lg"
            >
                <div
                    class="border-stone-gray/10 flex h-full min-h-0 w-full flex-col justify-between
                        border-r-2 py-4 pr-1 pl-4"
                >
                    <nav class="sidebar-scroll flex flex-col gap-4 overflow-y-auto pr-3">
                        <button
                            class="text-stone-gray/60 hover:bg-stone-gray/10 hover:text-soft-silk flex h-10
                                w-full items-center justify-start gap-3 rounded-lg px-3 text-left text-sm
                                font-semibold transition-colors duration-200 ease-in-out shrink-0"
                            @click="showHub"
                        >
                            <UiIcon name="MaterialSymbolsApps" class="h-5 w-5 shrink-0" />
                            <span>All Settings</span>
                        </button>

                        <div v-for="group in groups" :key="group.name">
                            <button
                                :class="[
                                    `flex h-11 w-full items-center justify-start gap-3 rounded-lg
                                    px-3 text-left font-semibold transition-colors duration-200
                                    ease-in-out`,
                                    {
                                        'text-ember-glow': selectedTab.group === group.name,
                                        [`text-stone-gray/60 hover:bg-stone-gray/10
                                        hover:text-soft-silk`]: selectedTab.group !== group.name,
                                    },
                                ]"
                                @click="selectGroup(group)"
                            >
                                <UiIcon :name="group.icon" class="h-5 w-5 shrink-0" />
                                <span>{{ group.name }}</span>
                            </button>
                            <ul
                                class="border-stone-gray/10 mt-2 ml-4 flex flex-col gap-1 border-l-2
                                    pl-5"
                            >
                                <li v-for="subTab in group.tabs" :key="subTab.name">
                                    <button
                                        :class="[
                                            `flex h-10 w-full items-center justify-start gap-3
                                            rounded-md px-3 text-left text-sm font-semibold
                                            transition-colors duration-200 ease-in-out`,
                                            {
                                                'bg-ember-glow/10 text-ember-glow':
                                                    selectedTab.name === subTab.name,
                                                [`text-stone-gray/60 hover:bg-stone-gray/10
                                                hover:text-soft-silk`]:
                                                    selectedTab.name !== subTab.name,
                                            },
                                        ]"
                                        @click="selectTab(subTab)"
                                    >
                                        <UiIcon :name="subTab.icon" class="h-5 w-5 shrink-0" />
                                        <span>{{ subTab.name }}</span>
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </nav>

                    <button
                        class="bg-ember-glow hover:bg-ember-glow/80 focus:shadow-outline
                            text-soft-silk mt-4 mr-3 w-full rounded-lg px-4 py-2.5 text-sm font-bold
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

<style scoped>
.sidebar-scroll {
    scrollbar-width: thin;
    scrollbar-color: transparent transparent;
    transition: scrollbar-color 0.3s;
}

.sidebar-scroll:hover {
    scrollbar-color: color-mix(in srgb, var(--color-stone-gray) 20%, transparent) transparent;
}

.sidebar-scroll::-webkit-scrollbar {
    width: 4px;
}

.sidebar-scroll::-webkit-scrollbar-track {
    background: transparent;
}

.sidebar-scroll::-webkit-scrollbar-thumb {
    background: transparent;
    border-radius: 9999px;
}

.sidebar-scroll:hover::-webkit-scrollbar-thumb {
    background: color-mix(in srgb, var(--color-stone-gray) 20%, transparent);
}

.sidebar-scroll::-webkit-scrollbar-thumb:hover {
    background: color-mix(in srgb, var(--color-stone-gray) 35%, transparent);
}
</style>
