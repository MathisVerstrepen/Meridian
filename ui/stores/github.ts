import { defineStore } from 'pinia';

import type { Repo } from '@/types/github';

const { apiFetch } = useAPI();

export const useGithubStore = defineStore('Github', () => {
    const repositories = ref<Repo[]>([]);
    const isLoadingRepos = ref(false);
    const isGithubConnected = ref(false);
    const githubUsername = ref<string | null>(null);

    let fetchPromise: Promise<Repo[]> | null = null;

    const fetchRepositories = async () => {
        if (fetchPromise) {
            return fetchPromise;
        }

        isLoadingRepos.value = true;
        try {
            fetchPromise = apiFetch<Repo[]>('/api/github/repos');
            const data = await fetchPromise;
            repositories.value = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch repositories:', error);
            repositories.value = [];
            throw error;
        } finally {
            isLoadingRepos.value = false;
            fetchPromise = null;
        }
    };

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

    watch(isGithubConnected, (newValue) => {
        if (newValue) {
            fetchRepositories();
        }
    });

    return {
        repositories,
        isLoadingRepos,
        isGithubConnected,
        githubUsername,

        fetchRepositories,
        checkGitHubStatus,
    };
});
