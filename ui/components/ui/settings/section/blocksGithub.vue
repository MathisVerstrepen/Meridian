<script lang="ts" setup>
const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

// --- Composables ---
const { apiFetch } = useAPI();

// --- Local State ---
const isGitHubConnected = ref(false);
const isLoading = ref(true);
const githubUsername = ref<string | null>(null);

// --- Core Logic Functions ---
async function checkGitHubStatus() {
    try {
        const data = await apiFetch<{ isConnected: boolean; username?: string }>(
            '/api/auth/github/status',
        );
        if (data.isConnected && data.username) {
            isGitHubConnected.value = true;
            githubUsername.value = data.username;
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
        isLoading.value = true;
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
            console.log('Successfully connected GitHub account!');
        } catch (error) {
            console.error('GitHub connection error:', error);
            isGitHubConnected.value = false;
        } finally {
            window.history.replaceState({}, document.title, window.location.pathname);
            isLoading.value = false;
        }
    } else {
        await checkGitHubStatus();
        isLoading.value = false;
    }
});
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2 self-center">
            <h3 class="text-stone-gray font-bold">GitHub App Connect</h3>
            <UiSettingsInfobubble>
                Connect your GitHub account to enable repository access.
            </UiSettingsInfobubble>
        </label>

        <!-- Loading State -->
        <div
            v-if="isLoading"
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
    </div>
</template>
