<script lang="ts" setup>
import {
    UiSettingsSectionGeneral,
    UiSettingsSectionModels,
    UiSettingsSectionModelsDropdown,
    UiSettingsSectionAccount,
} from '#components';

// --- Page Meta ---
definePageMeta({ middleware: 'auth' });

const route = useRoute();

enum TabNames {
    GENERAL = 'general',
    MODELS = 'models',
    MODELS_DROPDOWN = 'dropdown',
}

interface ITab {
    name: string;
    group: string;
    component: any;
    subTabs?: ITab[];
}

const Tabs = {
    GENERAL: {
        name: TabNames.GENERAL,
        group: TabNames.GENERAL,
        component: markRaw(UiSettingsSectionGeneral),
        subTabs: [],
    } as ITab,
    ACCOUNT: {
        name: 'account',
        group: TabNames.GENERAL,
        component: markRaw(UiSettingsSectionAccount),
        subTabs: [],
    } as ITab,
    MODELS: {
        name: TabNames.MODELS,
        group: TabNames.MODELS,
        component: markRaw(UiSettingsSectionModels),
        subTabs: [
            {
                name: TabNames.MODELS_DROPDOWN,
                group: TabNames.MODELS,
                component: markRaw(UiSettingsSectionModelsDropdown),
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
const backToLastPage = () => {
    history.back();
};

// --- Watchers ---
watch(selectedTab, (newTab) => {
    document.title = 'Settings - ' + newTab.name.charAt(0).toUpperCase() + newTab.name.slice(1);
    history.replaceState({}, '', window.location.pathname + '?tab=' + newTab.name);
});
</script>

<template>
    <div class="flex h-full w-full max-w-[1700px] flex-col justify-center gap-8 px-20 py-20">
        <div class="flex w-full items-center justify-between">
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
            class="bg-anthracite/75 border-stone-gray/10 grid h-full w-full grid-cols-[20%_80%] rounded-2xl border-2
                px-5 py-10 shadow-lg"
        >
            <div class="border-stone-gray/10 h-full w-full border-r-2 px-5">
                <ul>
                    <li v-for="tab in Object.values(Tabs)" class="mb-2">
                        <button
                            :class="{
                                'bg-stone-gray/10 text-stone-gray': selectedTab.name === tab.name,
                                'text-stone-gray/50 hover:bg-stone-gray/10 hover:text-stone-gray':
                                    selectedTab.name !== tab.name,
                            }"
                            class="flex h-12 w-full items-center justify-start rounded-lg px-4 font-bold capitalize transition-colors
                                duration-200 ease-in-out"
                            @click="selectedTab = tab"
                        >
                            {{ tab.name }}
                        </button>
                        <ul
                            v-if="tab.subTabs"
                            class="mt-2 ml-4"
                            v-show="selectedTab.group === tab.group"
                        >
                            <li v-for="subTab in tab.subTabs" :key="subTab.name" class="mb-2">
                                <button
                                    :class="{
                                        'bg-stone-gray/10 text-stone-gray':
                                            selectedTab.name === subTab.name,
                                        'text-stone-gray/50 hover:bg-stone-gray/10 hover:text-stone-gray':
                                            selectedTab.name !== subTab.name,
                                    }"
                                    class="flex h-12 w-full items-center justify-start rounded-lg px-4 font-bold capitalize transition-colors
                                        duration-200 ease-in-out"
                                    @click="selectedTab = subTab"
                                >
                                    {{ subTab.name }}
                                </button>
                            </li>
                        </ul>
                    </li>
                </ul>
            </div>

            <UiSettingsSectionLayout>
                <template #header>
                    {{ selectedTab.name }}
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
