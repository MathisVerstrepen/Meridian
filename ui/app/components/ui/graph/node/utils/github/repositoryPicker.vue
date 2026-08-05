<script lang="ts" setup>
import type { RepositoryInfo, SourceProvider } from '@/types/github';

const emit = defineEmits<{
    (e: 'select', repository: RepositoryInfo): void;
}>();

const repositoryStore = useRepositoryStore();
const { repositories, isLoading } = storeToRefs(repositoryStore);
const { fetchRepositories } = repositoryStore;
const { error } = useToast();

const searchInput = ref<HTMLInputElement | null>(null);
const query = ref('');
const selectedProvider = ref<SourceProvider>('github');
const fetchFailed = ref(false);

const isGitlab = (repository: RepositoryInfo) => repository.provider.startsWith('gitlab');

const providerRepositories = computed(() =>
    repositories.value.filter((repository) =>
        selectedProvider.value === 'gitlab' ? isGitlab(repository) : !isGitlab(repository),
    ),
);

const normalizedQuery = computed(() => query.value.trim().toLowerCase());
const filteredRepositories = computed(() => {
    if (!normalizedQuery.value) return providerRepositories.value;
    return providerRepositories.value.filter((repository) => {
        const description = repository.description?.toLowerCase() ?? '';
        return (
            repository.full_name.toLowerCase().includes(normalizedQuery.value) ||
            description.includes(normalizedQuery.value)
        );
    });
});

const loadRepositories = async () => {
    fetchFailed.value = false;
    try {
        await fetchRepositories();
    } catch {
        fetchFailed.value = true;
        error('Failed to fetch repositories');
    }
};

onMounted(async () => {
    await nextTick();
    searchInput.value?.focus();
    await loadRepositories();
});
</script>

<template>
    <section class="flex h-full min-h-0 w-full flex-col" aria-labelledby="repository-picker-title">
        <header class="mb-6 shrink-0 pr-14">
            <h1 id="repository-picker-title" class="text-soft-silk text-2xl font-bold">
                Select a repository
            </h1>
        </header>

        <div class="mb-6 flex shrink-0 flex-col gap-3 md:flex-row md:items-center">
            <label class="relative min-w-0 grow">
                <span class="sr-only">Search repositories…</span>
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/60 pointer-events-none absolute top-1/2 left-4 h-5 w-5
                        -translate-y-1/2"
                />
                <input
                    ref="searchInput"
                    v-model="query"
                    type="search"
                    aria-label="Search repositories…"
                    placeholder="Search repositories…"
                    class="bg-stone-gray/5 border-stone-gray/20 text-soft-silk placeholder:text-stone-gray/40
                        focus:border-ember-glow focus:ring-ember-glow/30 h-12 w-full rounded-xl border
                        pr-4 pl-12 text-base outline-none focus:ring-2"
                />
            </label>

            <div
                role="group"
                aria-label="Repository provider"
                class="bg-stone-gray/5 border-stone-gray/15 flex shrink-0 rounded-xl border p-1"
            >
                <button
                    v-for="provider in ['github', 'gitlab'] as const"
                    :key="provider"
                    type="button"
                    :aria-pressed="selectedProvider === provider"
                    class="focus-visible:ring-ember-glow flex min-h-10 flex-1 cursor-pointer items-center
                        justify-center gap-2 rounded-lg px-5 text-sm font-semibold outline-none
                        transition-colors focus-visible:ring-2 md:flex-none"
                    :class="
                        selectedProvider === provider
                            ? 'bg-stone-gray/20 text-soft-silk'
                            : 'text-stone-gray/60 hover:bg-stone-gray/10 hover:text-soft-silk'
                    "
                    @click="selectedProvider = provider"
                >
                    <UiIcon
                        :name="provider === 'gitlab' ? 'MdiGitlab' : 'MdiGithub'"
                        class="h-5 w-5"
                    />
                    {{ provider === 'gitlab' ? 'GitLab' : 'GitHub' }}
                </button>
            </div>
        </div>

        <div class="min-h-0 grow overflow-y-auto pr-1">
            <div
                v-if="isLoading"
                role="status"
                class="text-stone-gray/60 flex h-full min-h-48 items-center justify-center gap-3"
            >
                <UiIcon name="MingcuteLoading3Fill" class="h-6 w-6 animate-spin" />
                <span>Loading repositories…</span>
            </div>

            <div
                v-else-if="fetchFailed"
                role="alert"
                class="text-stone-gray/60 flex h-full min-h-48 flex-col items-center justify-center gap-4"
            >
                <span>Unable to load repositories.</span>
                <button
                    type="button"
                    class="bg-ember-glow/15 text-ember-glow hover:bg-ember-glow/25 focus-visible:ring-ember-glow
                        cursor-pointer rounded-lg px-4 py-2 font-semibold outline-none focus-visible:ring-2"
                    @click="loadRepositories"
                >
                    Try again
                </button>
            </div>

            <p
                v-else-if="repositories.length === 0"
                class="text-stone-gray/50 flex h-full min-h-48 items-center justify-center text-center"
            >
                No repositories available.
            </p>

            <p
                v-else-if="normalizedQuery && filteredRepositories.length === 0"
                class="text-stone-gray/50 flex h-full min-h-48 items-center justify-center text-center"
            >
                No repositories match your search.
            </p>

            <p
                v-else-if="providerRepositories.length === 0"
                class="text-stone-gray/50 flex h-full min-h-48 items-center justify-center text-center"
            >
                No repositories available for
                {{ selectedProvider === 'gitlab' ? 'GitLab' : 'GitHub' }}.
            </p>

            <ul
                v-else
                data-repository-grid
                class="grid grid-cols-1 gap-3 pb-2 lg:grid-cols-2 2xl:grid-cols-3"
            >
                <li v-for="repository in filteredRepositories" :key="repository.full_name">
                    <button
                        type="button"
                        class="bg-stone-gray/5 border-stone-gray/15 hover:bg-stone-gray/10
                            hover:border-stone-gray/30 focus-visible:border-ember-glow
                            focus-visible:ring-ember-glow/40 flex h-full min-h-36 w-full cursor-pointer
                            flex-col items-start rounded-xl border p-4 text-left outline-none transition-colors
                            focus-visible:ring-2"
                        @click="emit('select', repository)"
                    >
                        <span class="text-stone-gray/60 mb-3 flex items-center gap-2 text-xs font-semibold">
                            <UiIcon
                                :name="isGitlab(repository) ? 'MdiGitlab' : 'MdiGithub'"
                                class="h-4 w-4"
                            />
                            {{ isGitlab(repository) ? 'GitLab' : 'GitHub' }}
                        </span>
                        <span class="text-soft-silk w-full break-words font-semibold">
                            {{ repository.full_name }}
                        </span>
                        <span
                            v-if="repository.description?.trim()"
                            class="text-stone-gray/60 mt-2 line-clamp-2 text-sm"
                        >
                            {{ repository.description }}
                        </span>
                        <span class="text-stone-gray/50 mt-auto flex w-full items-center gap-4 pt-4 text-xs">
                            <span class="flex min-w-0 items-center gap-1">
                                <UiIcon name="MdiSourceBranch" class="h-4 w-4 shrink-0" />
                                <span class="truncate">{{ repository.default_branch || 'main' }}</span>
                            </span>
                            <span
                                v-if="typeof repository.stargazers_count === 'number'"
                                class="ml-auto flex shrink-0 items-center gap-1"
                            >
                                <UiIcon name="MaterialSymbolsStarOutlineRounded" class="h-4 w-4" />
                                {{ repository.stargazers_count }}
                            </span>
                        </span>
                    </button>
                </li>
            </ul>
        </div>
    </section>
</template>
