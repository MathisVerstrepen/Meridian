<script lang="ts" setup>
const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

// --- Store ---
const githubStore = useGithubStore();
const gitlabStore = useGitlabStore();
const repositoryStore = useRepositoryStore();
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { isGithubConnected, githubUsername } = storeToRefs(githubStore);
const { isGitlabConnected } = storeToRefs(gitlabStore);
const { blockGithubSettings } = storeToRefs(settingsStore);

// --- Actions/Methods from Stores ---
const { checkGitLabStatus } = gitlabStore;
const { checkGitHubStatus } = githubStore;
const { fetchRepositories } = repositoryStore;

// --- Composables ---
const { apiFetch, connectGitLab, disconnectGitLab } = useAPI();
const { success, error: toastError } = useToast();

// --- Local State ---
const isLoadingConnection = ref(true);
const isLoading = ref(true);
const personalAccessToken = ref('');
const privateKey = ref('');
const instanceUrl = ref('https://gitlab.com');

// --- Core Logic Functions ---
async function disconnectGitHub() {
    try {
        await apiFetch('/api/auth/github/disconnect', { method: 'POST' });
        await checkGitHubStatus();
        await fetchRepositories(true); // Force refresh repo list
    } catch (error) {
        console.error('Failed to disconnect GitHub:', error);
    }
}

function connectToGithub() {
    sessionStorage.setItem('preOauthUrl', window.history.state.back || '/');
    window.location.href = `${API_BASE_URL}/auth/github/login`;
}

async function connectToGitLab() {
    if (!personalAccessToken.value || !privateKey.value || !instanceUrl.value) {
        toastError('Instance URL, Personal Access Token, and SSH Private Key are required.');
        return;
    }
    try {
        isLoading.value = true;
        await connectGitLab(personalAccessToken.value, privateKey.value, instanceUrl.value);
        await checkGitLabStatus();
        await fetchRepositories(true);
        success(`Successfully connected to ${instanceUrl.value}.`);
        personalAccessToken.value = '';
        privateKey.value = '';
        instanceUrl.value = 'https://gitlab.com';
    } catch (error) {
        console.error('Failed to connect GitLab:', error);
        toastError('Failed to connect to GitLab. Please check your credentials and URL.');
    } finally {
        isLoading.value = false;
    }
}

async function disconnectFromGitLab() {
    try {
        isLoading.value = true;
        await disconnectGitLab();
        await checkGitLabStatus();
        await fetchRepositories(true);
        success('Successfully disconnected from GitLab.');
    } catch (error) {
        console.error('Failed to disconnect GitLab:', error);
        toastError('Failed to disconnect from GitLab.');
    } finally {
        isLoading.value = false;
    }
}

// --- Lifecycle Hooks ---
onMounted(async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
        isLoadingConnection.value = true;
        try {
            await apiFetch<{ message: string; username: string }>('/api/auth/github/callback', {
                method: 'POST',
                body: JSON.stringify({ code }),
            });
            await checkGitHubStatus();
            await fetchRepositories(true); // Force refresh repo list
        } catch (error) {
            console.error('GitHub connection error:', error);
        } finally {
            window.history.replaceState({}, document.title, window.location.pathname);
            isLoadingConnection.value = false;
        }
    } else {
        await checkGitHubStatus();
        await checkGitLabStatus();
        isLoadingConnection.value = false;
        isLoading.value = false;
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
                    class="border-stone-gray/20 text-soft-silk flex w-fit animate-pulse items-center
                        gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold"
                >
                    <UiIcon name="MdiGithub" class="h-5 w-5" />
                    <span>Checking...</span>
                </div>

                <!-- Connected State -->
                <div v-else-if="isGithubConnected" class="flex gap-2">
                    <div
                        class="border-olive-grove/30 bg-olive-grove/10 text-olive-grove flex w-fit
                            items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold
                            brightness-125"
                    >
                        <UiIcon name="MdiGithub" class="h-5 w-5" />
                        <span>Connected as {{ githubUsername }}</span>
                    </div>
                    <button
                        class="border-terracotta-clay-dark/30 bg-terracotta-clay-dark/10
                            text-terracotta-clay hover:bg-terracotta-clay-dark/20 flex w-fit
                            items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold
                            brightness-125 duration-200 ease-in-out hover:cursor-pointer"
                        @click="disconnectGitHub"
                    >
                        <span>Disconnect</span>
                    </button>
                </div>

                <!-- Not Connected State -->
                <button
                    v-else
                    id="block-github-app-connect"
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk
                        border-stone-gray/20 flex w-fit items-center gap-2 rounded-lg border-2 px-4
                        py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                        focus:outline-none"
                    @click.prevent="connectToGithub"
                >
                    <UiIcon name="MdiGithub" class="h-5 w-5" />
                    <span>Connect GitHub</span>
                </button>
            </div>
        </div>

        <!-- Setting: GitLab Connection -->
        <div class="flex items-start justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">GitLab Connection</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Connect your GitLab account using a Personal Access Token (PAT) and an SSH key
                    to access your private repositories.
                </p>
                <a
                    href="https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html"
                    target="_blank"
                    class="text-ember-glow/80 hover:text-ember-glow mt-2 inline-block text-sm
                        underline"
                >
                    How to create a PAT
                </a>
                <br />
                <a
                    href="https://docs.gitlab.com/ee/user/ssh.html"
                    target="_blank"
                    class="text-ember-glow/80 hover:text-ember-glow mt-1 inline-block text-sm
                        underline"
                >
                    How to create and add an SSH key
                </a>
            </div>
            <div class="ml-6 shrink-0">
                <!-- Loading State -->
                <div
                    v-if="isLoading"
                    class="border-stone-gray/20 text-soft-silk flex w-fit animate-pulse items-center
                        gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold"
                >
                    <UiIcon name="MdiGitlab" class="h-5 w-5" />
                    <span>Checking...</span>
                </div>

                <!-- Connected State -->
                <div v-else-if="isGitlabConnected" class="flex gap-2">
                    <div
                        class="border-olive-grove/30 bg-olive-grove/10 text-olive-grove flex w-fit
                            items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold
                            brightness-125"
                    >
                        <UiIcon name="MdiGitlab" class="h-5 w-5" />
                        <span>Connected to GitLab</span>
                    </div>
                    <button
                        class="border-terracotta-clay-dark/30 bg-terracotta-clay-dark/10
                            text-terracotta-clay hover:bg-terracotta-clay-dark/20 flex w-fit
                            items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold
                            brightness-125 duration-200 ease-in-out hover:cursor-pointer"
                        @click="disconnectFromGitLab"
                    >
                        <span>Disconnect</span>
                    </button>
                </div>

                <!-- Not Connected State -->
                <div v-else class="flex w-96 flex-col gap-4">
                    <input
                        v-model="instanceUrl"
                        type="text"
                        placeholder="GitLab Instance URL"
                        class="bg-obsidian/50 border-stone-gray/20 text-soft-silk w-full rounded-lg
                            border-2 px-3 py-2 text-sm focus:outline-none"
                    />
                    <input
                        v-model="personalAccessToken"
                        type="password"
                        placeholder="GitLab Personal Access Token"
                        class="bg-obsidian/50 border-stone-gray/20 text-soft-silk w-full rounded-lg
                            border-2 px-3 py-2 text-sm focus:outline-none"
                    />
                    <textarea
                        v-model="privateKey"
                        placeholder="SSH Private Key (-----BEGIN OPENSSH PRIVATE KEY-----...)"
                        rows="4"
                        class="bg-obsidian/50 border-stone-gray/20 text-soft-silk dark-scrollbar
                            w-full rounded-lg border-2 px-3 py-2 font-mono text-sm
                            focus:outline-none"
                    />
                    <button
                        id="block-gitlab-connect"
                        class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk
                            border-stone-gray/20 flex w-full items-center justify-center gap-2
                            rounded-lg border-2 px-4 py-2 text-sm font-bold duration-200 ease-in-out
                            hover:cursor-pointer focus:outline-none"
                        @click.prevent="connectToGitLab"
                    >
                        <UiIcon name="MdiGitlab" class="h-5 w-5" />
                        <span>Connect GitLab</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- Setting: Auto Pull -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Auto Pull</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Automatically pull the latest changes from the repository. This is triggered
                    when a block using the repository is executed or when you open the file
                    selection.
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
