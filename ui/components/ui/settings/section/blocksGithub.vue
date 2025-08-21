<script lang="ts" setup>
import type { Repo } from '@/types/github';

const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

// --- Composables ---
const { apiFetch } = useAPI();

// --- Local State ---
const isGitHubConnected = ref(false);
const isLoadingConnection = ref(true);
const githubUsername = ref<string | null>(null);

const repositories = ref<Repo[]>([]);
const isLoadingRepos = ref(false);
const searchQuery = ref('');
const sortBy = ref<'pushed_at' | 'full_name' | 'stargazers_count'>('pushed_at');

// --- Computed Properties ---
const filteredAndSortedRepos = computed(() => {
    if (!repositories.value) return [];

    return repositories.value
        .filter((repo) => repo.full_name.toLowerCase().includes(searchQuery.value.toLowerCase()))
        .sort((a, b) => {
            switch (sortBy.value) {
                case 'full_name':
                    return a.full_name.localeCompare(b.full_name);
                case 'stargazers_count':
                    return b.stargazers_count - a.stargazers_count;
                case 'pushed_at':
                default:
                    return new Date(b.pushed_at).getTime() - new Date(a.pushed_at).getTime();
            }
        });
});

// --- Core Logic Functions ---
async function fetchRepositories() {
    isLoadingRepos.value = true;
    try {
        const data = await apiFetch<Repo[]>('/api/github/repos');
        repositories.value = data;
    } catch (error) {
        console.error('Failed to fetch repositories:', error);
        repositories.value = [];
    } finally {
        isLoadingRepos.value = false;
    }
}

async function checkGitHubStatus() {
    try {
        const data = await apiFetch<{ isConnected: boolean; username?: string }>(
            '/api/auth/github/status',
        );
        if (data.isConnected && data.username) {
            isGitHubConnected.value = true;
            githubUsername.value = data.username;
            await fetchRepositories();
        } else {
            isGitHubConnected.value = false;
            githubUsername.value = null;
        }
    } catch (error) {
        console.error('Failed to check GitHub status:', error);
        isGitHubConnected.value = false;
    }
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
                    body: { code },
                },
            );
            isGitHubConnected.value = true;
            githubUsername.value = data.username;
            await fetchRepositories();
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
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <!-- GitHub Connection Row -->
        <label class="flex gap-2 self-center">
            <h3 class="text-stone-gray font-bold">GitHub App Connect</h3>
            <UiSettingsInfobubble>
                Connect your GitHub account to enable repository access.
            </UiSettingsInfobubble>
        </label>

        <!-- Loading State -->
        <div
            v-if="isLoadingConnection"
            class="border-stone-gray/20 dark:text-soft-silk text-obsidian flex w-fit animate-pulse items-center gap-2
                rounded-lg border-2 px-4 py-2 text-sm font-bold"
        >
            <UiIcon name="MdiGithub" class="h-5 w-5" />
            <span>Checking...</span>
        </div>

        <!-- Connected State -->
        <div
            v-else-if="isGitHubConnected"
            class="border-olive-grove/30 bg-olive-grove/10 text-olive-grove flex w-fit items-center gap-2 rounded-lg
                border-2 px-4 py-2 text-sm font-bold brightness-125"
        >
            <UiIcon name="MdiGithub" class="h-5 w-5" />
            <span>Connected as {{ githubUsername }}</span>
        </div>

        <!-- Not Connected State -->
        <a
            v-else
            id="block-github-app-connect"
            class="hover:bg-stone-gray/10 focus:shadow-outline dark:text-soft-silk text-obsidian border-stone-gray/20
                flex w-fit items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold duration-200
                ease-in-out hover:cursor-pointer focus:outline-none"
            :href="`${API_BASE_URL}/auth/github/login`"
        >
            <UiIcon name="MdiGithub" class="h-5 w-5" />
            <span>Connect GitHub</span>
        </a>

        <!-- Repositories Row -->
        <label class="flex gap-2 self-start pt-2">
            <h3 class="text-stone-gray font-bold">Repositories</h3>
            <UiSettingsInfobubble
                >Search and select repositories to use in your projects.</UiSettingsInfobubble
            >
        </label>

        <div v-if="isGitHubConnected" class="flex flex-col gap-4">
            <!-- Search and Sort Controls -->
            <div class="flex items-center gap-4 text-stone-gray/70">
                <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="Search repositories..."
                    class="dark:bg-obsidian/50 border-stone-gray/20 w-full rounded-md border-2 bg-white px-3 py-1.5 text-sm"
                />
                <select
                    v-model="sortBy"
                    class="dark:bg-obsidian/50 border-stone-gray/20 rounded-md border-2 bg-white px-3 py-1.5 text-sm"
                >
                    <option value="pushed_at" class="text-obsidian">Last Updated</option>
                    <option value="full_name" class="text-obsidian">Name</option>
                    <option value="stargazers_count" class="text-obsidian">Stars</option>
                </select>
            </div>

            <!-- Repository List -->
            <div v-if="isLoadingRepos" class="text-stone-gray/70 text-center">
                Loading repositories...
            </div>
            <div v-else-if="!filteredAndSortedRepos.length" class="text-stone-gray/70 text-center">
                No repositories found.
            </div>
            <ul
                v-else
                class="dark:bg-obsidian/30 border-stone-gray/20 h-72 max-h-72 space-y-2 overflow-y-auto rounded-lg border-2
                    p-2"
            >
                <li
                    v-for="repo in filteredAndSortedRepos"
                    :key="repo.id"
                    class="hover:bg-stone-gray/10 flex cursor-pointer items-center justify-between rounded-md p-2"
                >
                    <div class="flex items-center gap-2">
                        <UiIcon
                            v-if="repo.private"
                            name="MaterialSymbolsLockOutline"
                            class="h-4 w-4 text-golden-ochre"
                            title="Private Repository"
                        />
                        <UiIcon
                            v-else
                            name="MaterialSymbolsLockOpenRightOutlineRounded"
                            class="text-stone-gray/70 h-4 w-4"
                            title="Public Repository"
                        />
                        <span class="text-sm text-stone-gray/70">{{ repo.full_name }}</span>
                    </div>
                    <span
                        v-if="repo.private"
                        class="rounded-full bg-golden-ochre/20 px-2 py-0.5 text-xs text-golden-ochre"
                        >Private</span
                    >
                </li>
            </ul>
        </div>
        <div v-else class="text-stone-gray/50 self-start pt-2 italic">
            Connect your GitHub account to see your repositories.
        </div>
    </div>
</template>
