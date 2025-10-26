import { defineStore } from 'pinia';
import type { RepositoryInfo } from '@/types/github';

const { apiFetch } = useAPI();

export const useRepositoryStore = defineStore('Repository', () => {
    const repositories = ref<RepositoryInfo[]>([]);
    const isLoading = ref(false);
    let fetchPromise: Promise<RepositoryInfo[]> | null = null;

    const fetchRepositories = async (force: boolean = false) => {
        if (fetchPromise && !force) {
            return fetchPromise;
        }

        isLoading.value = true;
        try {
            fetchPromise = apiFetch<RepositoryInfo[]>('/api/repositories');
            const data = await fetchPromise;
            repositories.value = data;
            return data;
        } catch (error) {
            console.error('Failed to fetch repositories:', error);
            repositories.value = [];
            throw error;
        } finally {
            isLoading.value = false;
            fetchPromise = null;
        }
    };

    return {
        repositories,
        isLoading,
        fetchRepositories,
    };
});
