import { defineStore } from 'pinia';

import type { Repo } from '@/types/github';

const { apiFetch } = useAPI();

export const useGithubStore = defineStore('Github', () => {
    const repositories = ref<Repo[]>([]);
    const isLoadingRepos = ref(false);
    let fetchPromise: Promise<Repo[]> | null = null;

    const numberOfRepos = computed(() => repositories.value.length);

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

    return {
        repositories,
        isLoadingRepos,

        numberOfRepos,

        fetchRepositories,
    };
});
