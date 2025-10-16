<script lang="ts" setup>
const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

// --- Store ---
const githubStore = useGithubStore();
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { repositories, isGithubConnected, githubUsername } =
    storeToRefs(githubStore);
const { blockGithubSettings } = storeToRefs(settingsStore);

// --- Actions/Methods from Stores ---
const { checkGitHubStatus } = githubStore;

// --- Composables ---
const { apiFetch } = useAPI();

// --- Local State ---
const isLoadingConnection = ref(true);

// const searchQuery = ref('');
// const sortBy = ref<'pushed_at' | 'full_name' | 'stargazers_count'>('pushed_at');

// --- Computed Properties ---
// const filteredAndSortedRepos = computed(() => {
//     if (!repositories.value) return [];

//     return repositories.value
//         .filter((repo) => repo.full_name.toLowerCase().includes(searchQuery.value.toLowerCase()))
//         .sort((a, b) => {
//             switch (sortBy.value) {
//                 case 'full_name':
//                     return a.full_name.localeCompare(b.full_name);
//                 case 'stargazers_count':
//                     return b.stargazers_count - a.stargazers_count;
//                 case 'pushed_at':
//                 default:
//                     return new Date(b.pushed_at).getTime() - new Date(a.pushed_at).getTime();
//             }
//         });
// });

// --- Core Logic Functions ---
async function disconnectGitHub() {
    try {
        await apiFetch('/api/auth/github/disconnect', { method: 'POST' });
        isGithubConnected.value = false;
        githubUsername.value = null;
        repositories.value = [];
    } catch (error) {
        console.error('Failed to disconnect GitHub:', error);
    }
}

function connectToGithub() {
    sessionStorage.setItem('preOauthUrl', window.history.state.back || '/');
    window.location.href = `${API_BASE_URL}/auth/github/login`;
}

// --- Lifecycle Hooks ---
onMounted(async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
        isLoadingConnection.value = true;
        try {
            const data = await apiFetch<{ message: string; username: string }>(
                '/api/auth/github/callback',
                {
                    method: 'POST',
                    body: JSON.stringify({ code }),
                },
            );
            isGithubConnected.value = true;
            githubUsername.value = data.username;
        } catch (error) {
            console.error('GitHub connection error:', error);
        } finally {
            window.history.replaceState({}, document.title, window.location.pathname);
            isLoadingConnection.value = false;
        }
    } else {
        await checkGitHubStatus();
        isLoadingConnection.value = false;
    }
});
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: GitHub Connection -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">GitHub App Connection</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Connect your GitHub account to enable repository access for use in blocks.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <!-- Loading State -->
                <div
                    v-if="isLoadingConnection"
                    class="border-stone-gray/20 text-soft-silk flex w-fit animate-pulse items-center gap-2 rounded-lg border-2
                        px-4 py-2 text-sm font-bold"
                >
                    <UiIcon name="MdiGithub" class="h-5 w-5" />
                    <span>Checking...</span>
                </div>

                <!-- Connected State -->
                <div v-else-if="isGithubConnected" class="flex gap-2">
                    <div
                        class="border-olive-grove/30 bg-olive-grove/10 text-olive-grove flex w-fit items-center gap-2 rounded-lg
                            border-2 px-4 py-2 text-sm font-bold brightness-125"
                    >
                        <UiIcon name="MdiGithub" class="h-5 w-5" />
                        <span>Connected as {{ githubUsername }}</span>
                    </div>
                    <button
                        class="border-terracotta-clay-dark/30 bg-terracotta-clay-dark/10 text-terracotta-clay
                            hover:bg-terracotta-clay-dark/20 flex w-fit items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm
                            font-bold brightness-125 duration-200 ease-in-out hover:cursor-pointer"
                        @click="disconnectGitHub"
                    >
                        <span>Disconnect</span>
                    </button>
                </div>

                <!-- Not Connected State -->
                <button
                    v-else
                    id="block-github-app-connect"
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk border-stone-gray/20 flex w-fit
                        items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold duration-200 ease-in-out
                        hover:cursor-pointer focus:outline-none"
                    @click.prevent="connectToGithub"
                >
                    <UiIcon name="MdiGithub" class="h-5 w-5" />
                    <span>Connect GitHub</span>
                </button>
            </div>
        </div>

        <!-- Setting: Repositories -->
        <!-- Will be implemented later -->
        <!-- <div class="py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Repositories</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Search and select repositories to use in your projects.
                </p>
            </div>

            <div v-if="isGithubConnected" class="mt-4 flex flex-col gap-4">
                <div class="text-stone-gray/70 flex items-center gap-4">
                    <input
                        v-model="searchQuery"
                        type="text"
                        placeholder="Search repositories..."
                        class="bg-obsidian/50 border-stone-gray/20 w-full rounded-md border-2 px-3 py-1.5 text-sm"
                    />
                    <select
                        v-model="sortBy"
                        class="bg-obsidian/50 border-stone-gray/20 rounded-md border-2 px-3 py-1.5 text-sm"
                    >
                        <option value="pushed_at">Last Updated</option>
                        <option value="full_name">Name</option>
                        <option value="stargazers_count">Stars</option>
                    </select>
                </div>

                <div v-if="isLoadingRepos" class="text-stone-gray/70 pt-4 text-center">
                    Loading repositories...
                </div>
                <div
                    v-else-if="!filteredAndSortedRepos.length"
                    class="text-stone-gray/70 pt-4 text-center"
                >
                    No repositories found.
                </div>
                <ul
                    v-else
                    class="bg-obsidian/30 border-stone-gray/20 custom_scroll h-72 max-h-72 space-y-2 overflow-y-auto rounded-lg
                        border-2 p-2"
                >
                </ul>
            </div>
            <div v-else class="text-stone-gray/50 mt-4 italic">
                Connect your GitHub account to see your repositories.
            </div>
        </div> -->

        <!-- Setting: Auto Pull -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Auto Pull</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Automatically pull the latest changes from the GitHub repository. This is
                    triggered when a block using the repository is executed or when you open the
                    file selection.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="github-auto-pull"
                    :state="blockGithubSettings.autoPull"
                    :set-state="
                        (value: boolean) => {
                            blockGithubSettings.autoPull = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
