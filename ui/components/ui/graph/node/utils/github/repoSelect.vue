<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller';

import { SavingStatus } from '@/types/enums';
import type { Repo } from '@/types/github';

// --- Stores ---
const githubStore = useGithubStore();
const canvasSaveStore = useCanvasSaveStore();

// --- State from Stores ---
const { repositories, numberOfRepos } = storeToRefs(githubStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;
const { fetchRepositories } = githubStore;

// --- Props ---
const props = defineProps<{
    repo: Repo | undefined;
    setRepo: (repo: Repo | undefined) => void;
}>();

// --- Local State ---
const comboboxInput = ref<HTMLInputElement>();
const selected = ref<Repo | undefined | null>();
const query = ref<string>('');

// --- Computed Properties ---
const filteredRepos = computed(() => {
    if (!query.value) return repositories.value;
    return repositories.value.filter((repo) =>
        repo.full_name.toLowerCase().includes(query.value.toLowerCase()),
    );
});

// --- Core logic ---
const clearSelection = async (event: MouseEvent) => {
    event.stopPropagation();

    query.value = '';
    selected.value = null;

    await nextTick();
    if (comboboxInput.value) {
        comboboxInput.value.value = '';
    }
};

watch(selected, (newSelected) => {
    props.setRepo(newSelected ?? undefined);

    setNeedSave(SavingStatus.NOT_SAVED);
});

watch(query, (newquery) => {
    console.log(newquery);
});

onMounted(async () => {
    if (numberOfRepos.value === 0) {
        await fetchRepositories();
    }

    selected.value = props.repo;

    console.log('Repositories fetched:', repositories.value);
});
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative w-full">
            <div
                class="bg-soft-silk/10 border-soft-silk/10 text-soft-silk relative flex h-9 w-full cursor-default
                    items-center justify-center overflow-hidden rounded-2xl border-2 text-left focus:outline-none"
            >
                <HeadlessComboboxButton class="w-full">
                    <div v-if="!selected" class="flex items-center gap-2 pl-3">
                        <HeadlessComboboxInput
                            ref="comboboxInput"
                            class="relative w-full border-none py-1 pr-10 text-sm leading-5 focus:ring-0 focus:outline-none"
                            :displayValue="(repo: unknown) => (repo as Repo)?.full_name ?? ''"
                            @change="query = $event.target.value"
                            placeholder="Search for a repository..."
                        />
                    </div>

                    <div v-else class="flex items-center justify-between gap-2 px-2 pr-8">
                        <UiGraphNodeUtilsGithubRepoSelectItem :repo="selected" />
                        <button
                            class="text-stone-gray hover:bg-stone-gray/10 flex cursor-pointer items-center justify-center rounded-full
                                p-1 duration-200 ease-in-out"
                            @click="clearSelection"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                        </button>
                    </div>

                    <span class="absolute inset-y-0 right-0 flex cursor-pointer items-center pr-1">
                        <UiIcon name="FlowbiteChevronDownOutline" class="h-7 w-7" />
                    </span>
                </HeadlessComboboxButton>
            </div>

            <HeadlessTransitionRoot
                leave="transition ease-in duration-100"
                leaveFrom="opacity-100"
                leaveTo="opacity-0"
                @after-leave="query = ''"
            >
                <HeadlessComboboxOptions
                    class="bg-soft-silk/10 absolute z-40 mt-1 h-fit w-full rounded-md p-1 text-base shadow-lg ring-1
                        ring-black/5 backdrop-blur-2xl focus:outline-none"
                >
                    <DynamicScroller
                        v-if="filteredRepos.length"
                        ref="scrollerRef"
                        :items="filteredRepos"
                        :min-item-size="40"
                        key-field="id"
                        class="nowheel dark-scrollbar max-h-60"
                    >
                        <template #default="{ item: repo, index, active }">
                            <DynamicScrollerItem
                                :item="repo"
                                :active="active"
                                :data-index="index ?? -1"
                            >
                                <template v-if="typeof index === 'number'">
                                    <HeadlessComboboxOption
                                        :value="repo"
                                        as="div"
                                        v-slot="{ selected, active }"
                                        class="hover:bg-stone-gray/10 flex cursor-pointer items-center justify-between rounded-md p-2"
                                    >
                                        <UiGraphNodeUtilsGithubRepoSelectItem :repo="repo" />
                                    </HeadlessComboboxOption>
                                </template>
                            </DynamicScrollerItem>
                        </template>
                    </DynamicScroller>

                    <div v-else class="relative cursor-default px-4 py-2 text-gray-700 select-none">
                        Nothing found.
                    </div>
                </HeadlessComboboxOptions>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped>
</style>
