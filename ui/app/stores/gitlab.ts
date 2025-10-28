import { defineStore } from 'pinia';

const { apiFetch } = useAPI();

export const useGitlabStore = defineStore('GitLab', () => {
    const isGitlabConnected = ref(false);

    const checkGitLabStatus = async () => {
        try {
            const data = await apiFetch<{ isConnected: boolean }>('/api/auth/gitlab/status');
            isGitlabConnected.value = data.isConnected;
        } catch (error) {
            console.error('Failed to check GitLab status:', error);
            isGitlabConnected.value = false;
        }
    };

    return {
        isGitlabConnected,
        checkGitLabStatus,
    };
});
