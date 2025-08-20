<script lang="ts" setup>
const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

const { apiFetch } = useAPI();

const isGitHubConnected = ref(false); 
const isLoading = ref(false);

onMounted(async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
        isLoading.value = true;
        try {
            // Send the code to backend to exchange it for a token
            await apiFetch<any>('/api/auth/github/callback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code }),
            });

            isGitHubConnected.value = true;
            console.log('Successfully connected GitHub account!');
        } catch (error) {
            console.error('GitHub connection error:', error);
        } finally {
            isLoading.value = false;
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }
});
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2 self-center" for="block-github-app-connect">
            <h3 class="text-stone-gray font-bold">GitHub App Connect</h3>
            <UiSettingsInfobubble>
                Connect your GitHub account to enable repository access.
            </UiSettingsInfobubble>
        </label>

        <a
            id="block-github-app-connect"
            class="hover:bg-stone-gray/10 focus:shadow-outline dark:text-soft-silk text-obsidian border-stone-gray/20
                flex w-fit items-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-bold duration-200
                ease-in-out hover:cursor-pointer focus:outline-none"
            :href="`${API_BASE_URL}/auth/github/login`"
            :class="{
                'animate-pulse': isLoading,
            }"
        >
            <UiIcon name="MdiGithub" class="h-5 w-5" />
            <span v-if="isLoading">Connecting...</span>
            <span v-else-if="isGitHubConnected">Connected</span>
            <span v-else>Connect GitHub</span>
        </a>
    </div>
</template>

<style scoped></style>
