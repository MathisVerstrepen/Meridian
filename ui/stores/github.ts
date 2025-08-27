import { defineStore } from 'pinia';

import type { Repo } from '@/types/github';

const { apiFetch } = useAPI();

export const useGithubStore = defineStore('Github', () => {
    const repositories = ref<Repo[]>([]);
    const isLoadingRepos = ref(false);

    const numberOfRepos = computed(() => repositories.value.length);

    const fetchRepositories = async () => {
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
    };

    return {
        repositories,
        isLoadingRepos,

        numberOfRepos,

        fetchRepositories,
    };
});
