<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller';

import { SavingStatus } from '@/types/enums';
import type { RepositoryInfo, SourceProvider } from '@/types/github';

const currentRepo = defineModel<RepositoryInfo>('currentRepo');

// --- Stores ---
const repositoryStore = useRepositoryStore();
const canvasSaveStore = useCanvasSaveStore();

// --- State from Stores ---
const { repositories, isLoading } = storeToRefs(repositoryStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;

// --- Local State ---
const comboboxInput = ref<HTMLInputElement>();
const selected = ref<RepositoryInfo | undefined | null>(currentRepo.value);
const query = ref<string>('');
const selectedSource = ref<SourceProvider>('github');

// --- Computed Properties ---
const filteredRepos = computed(() => {
    return repositories.value
        .filter((repo) => {
            const isGitlab = repo.provider.startsWith('gitlab');
            return selectedSource.value === 'gitlab' ? isGitlab : !isGitlab;
        })
        .filter((repo) => {
            if (!query.value) return true;
            return repo.full_name.toLowerCase().includes(query.value.toLowerCase());
        });
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
    currentRepo.value = newSelected ?? undefined;

    setNeedSave(SavingStatus.NOT_SAVED);
});

// Sync model with local selected & set source tab
watch(
    currentRepo,
    (newRepo) => {
        if (selected.value?.full_name !== newRepo?.full_name) {
            selected.value = newRepo;
        }
        if (newRepo && newRepo.provider) {
            selectedSource.value = newRepo.provider.startsWith('gitlab') ? 'gitlab' : 'github';
        }
    },
    { immediate: true },
);

// When switching source, if the selected repo is not from that source, deselect it
watch(selectedSource, (newSource, oldSource) => {
    if (newSource === oldSource || !selected.value) return;

    const isSelectedGitlab = selected.value?.provider?.startsWith('gitlab') || false;
    if (
        (newSource === 'github' && isSelectedGitlab) ||
        (newSource === 'gitlab' && !isSelectedGitlab)
    ) {
        selected.value = null;
    }
});
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative w-full">
            <div
                class="bg-soft-silk/10 border-soft-silk/10 text-soft-silk relative flex h-9 w-full
                    cursor-default items-center justify-center overflow-hidden rounded-2xl border-2
                    text-left focus:outline-none"
            >
                <HeadlessComboboxButton class="w-full">
                    <div v-if="!selected && !isLoading" class="flex items-center gap-2 pl-3">
                        <HeadlessComboboxInput
                            ref="comboboxInput"
                            class="placeholder:text-soft-silk/25 relative w-full border-none
                                bg-transparent py-1 pr-10 text-sm leading-5 focus:ring-0
                                focus:outline-none"
                            :display-value="
                                (repo: unknown) => (repo as RepositoryInfo)?.full_name ?? ''
                            "
                            placeholder="Search for a repository..."
                            @change="query = $event.target.value"
                        />
                    </div>

                    <div
                        v-if="isLoading"
                        class="text-soft-silk/50 flex animate-pulse items-center justify-center py-2
                            text-xs font-bold"
                    >
                        Loading repositories...
                    </div>

                    <div
                        v-if="!isLoading && selected"
                        class="flex items-center justify-between gap-2 overflow-hidden px-2 pr-8"
                    >
                        <UiGraphNodeUtilsGithubRepoSelectItem :repo="selected" />
                        <button
                            class="text-stone-gray hover:bg-stone-gray/10 flex cursor-pointer
                                items-center justify-center rounded-full p-1 duration-200
                                ease-in-out"
                            @click="clearSelection"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                        </button>
                    </div>

                    <span
                        class="text-stone-gray absolute inset-y-0 right-0 flex cursor-pointer
                            items-center pr-1"
                    >
                        <UiIcon
                            v-if="!isLoading"
                            name="FlowbiteChevronDownOutline"
                            class="h-7 w-7"
                        />
                    </span>
                </HeadlessComboboxButton>
            </div>

            <HeadlessTransitionRoot
                leave="transition ease-in duration-100"
                leave-from="opacity-100"
                leave-to="opacity-0"
                @after-leave="query = ''"
            >
                <HeadlessComboboxOptions
                    class="bg-soft-silk/10 absolute z-40 mt-1 h-fit w-full rounded-md p-1 text-base
                        shadow-lg ring-1 ring-black/5 backdrop-blur-2xl focus:outline-none"
                >
                    <div class="border-soft-silk/10 mb-1 flex items-center gap-1 border-b pb-1">
                        <button
                            :class="[
                                `flex flex-1 items-center justify-center gap-1 rounded-md px-3 py-1
                                text-sm font-medium duration-200`,
                                selectedSource === 'github'
                                    ? 'bg-stone-gray/20 text-soft-silk'
                                    : 'text-soft-silk/70 hover:bg-stone-gray/10',
                            ]"
                            @click="selectedSource = 'github'"
                        >
                            <UiIcon name="MdiGithub" class="text-soft-silk h-4 w-4" />
                            GitHub
                        </button>
                        <button
                            :class="[
                                `flex flex-1 items-center justify-center gap-1 rounded-md px-3 py-1
                                text-sm font-medium duration-200`,
                                selectedSource === 'gitlab'
                                    ? 'bg-stone-gray/20 text-soft-silk'
                                    : 'text-soft-silk/70 hover:bg-stone-gray/10',
                            ]"
                            @click="selectedSource = 'gitlab'"
                        >
                            <UiIcon name="MdiGitlab" class="text-soft-silk h-4 w-4" />
                            GitLab
                        </button>
                    </div>

                    <DynamicScroller
                        v-if="filteredRepos.length"
                        ref="scrollerRef"
                        :items="filteredRepos"
                        :min-item-size="40"
                        :key-field="'full_name'"
                        class="nowheel dark-scrollbar max-h-60"
                    >
                        <template #default="{ item: filteredRepo, index, active }">
                            <DynamicScrollerItem
                                :item="filteredRepo"
                                :active="active"
                                :data-index="index ?? -1"
                            >
                                <template v-if="typeof index === 'number'">
                                    <HeadlessComboboxOption
                                        :value="filteredRepo"
                                        as="div"
                                        class="hover:bg-stone-gray/10 flex cursor-pointer
                                            items-center justify-between rounded-md p-2"
                                    >
                                        <UiGraphNodeUtilsGithubRepoSelectItem
                                            :repo="filteredRepo"
                                        />
                                    </HeadlessComboboxOption>
                                </template>
                            </DynamicScrollerItem>
                        </template>
                    </DynamicScroller>

                    <div
                        v-else
                        class="text-soft-silk/50 relative cursor-default px-4 py-2 select-none"
                    >
                        Nothing found.
                    </div>
                </HeadlessComboboxOptions>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped></style>
