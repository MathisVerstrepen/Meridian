import { defineStore } from 'pinia';

const { apiFetch } = useAPI();

export const useGithubStore = defineStore('Github', () => {
    const isGithubConnected = ref(false);
    const githubUsername = ref<string | null>(null);

    const checkGitHubStatus = async () => {
        try {
            const data = await apiFetch<{ isConnected: boolean; username?: string }>(
                '/api/auth/github/status',
            );
            if (data.isConnected && data.username) {
                isGithubConnected.value = true;
                githubUsername.value = data.username;
            } else {
                isGithubConnected.value = false;
                githubUsername.value = null;
            }
        } catch (error) {
            console.error('Failed to check GitHub status:', error);
            isGithubConnected.value = false;
        }
    };

    return {
        isGithubConnected,
        githubUsername,
        checkGitHubStatus,
    };
});
