import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { ref } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RepositoryPicker from '@/components/ui/graph/node/utils/github/repositoryPicker.vue';
import type { RepositoryInfo } from '@/types/github';

const stubs = vi.hoisted(() => ({
    repositoryValues: Array<RepositoryInfo>(),
    loading: false,
    fetchRepositories: vi.fn(),
    error: vi.fn(),
}));

mockNuxtImport('useRepositoryStore', () => () => ({
    storeKind: 'repository',
    fetchRepositories: stubs.fetchRepositories,
}));
mockNuxtImport('storeToRefs', () => () => ({
    repositories: ref(stubs.repositoryValues),
    isLoading: ref(stubs.loading),
}));
mockNuxtImport('useToast', () => () => ({ error: stubs.error }));

const githubRepo: RepositoryInfo = {
    provider: 'github',
    encoded_provider: 'github',
    full_name: 'meridian/frontend',
    description: 'Frontend tools',
    clone_url_ssh: '',
    clone_url_https: '',
    default_branch: 'develop',
    stargazers_count: 0,
};

const githubRepoWithoutOptionalMetadata: RepositoryInfo = {
    ...githubRepo,
    full_name: 'meridian/api',
    description: null,
    default_branch: '',
    stargazers_count: undefined,
};

const gitlabRepo: RepositoryInfo = {
    ...githubRepo,
    provider: 'gitlab-self-hosted',
    encoded_provider: 'gitlab',
    full_name: 'meridian/deployment',
    description: 'Deployment automation',
    default_branch: 'main',
    stargazers_count: 5,
};

const mountPicker = () =>
    mountSuspended(RepositoryPicker, {
        attachTo: document.body,
        global: { stubs: { UiIcon: true } },
    });

describe('Git repository picker', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        stubs.repositoryValues = [
            githubRepo,
            githubRepoWithoutOptionalMetadata,
            gitlabRepo,
        ];
        stubs.loading = false;
        stubs.fetchRepositories.mockResolvedValue(stubs.repositoryValues);
    });

    it('focuses search, filters by provider and text, renders metadata, and emits selection', async () => {
        const wrapper = await mountPicker();
        await flushPromises();

        const search = wrapper.get('input[aria-label="Search repositories…"]');
        expect(document.activeElement).toBe(search.element);
        expect(wrapper.text()).toContain('Select a repository');
        expect(wrapper.text()).toContain('meridian/frontend');
        expect(wrapper.text()).toContain('Frontend tools');
        expect(wrapper.text()).toContain('develop');
        expect(wrapper.text()).toContain('0');
        expect(wrapper.text()).toContain('meridian/api');
        expect(wrapper.text()).toContain('main');
        expect(wrapper.text()).not.toContain('meridian/deployment');

        const frontendButton = wrapper
            .findAll('button')
            .find((button) => button.text().includes('meridian/frontend'));
        const apiButton = wrapper
            .findAll('button')
            .find((button) => button.text().includes('meridian/api'));
        expect(frontendButton?.text()).toContain('0');
        expect(apiButton?.text()).not.toContain('Frontend tools');

        await search.setValue(' frontend tools ');
        expect(wrapper.text()).toContain('meridian/frontend');
        expect(wrapper.text()).not.toContain('meridian/api');

        await search.setValue('deployment automation');
        await wrapper.get('button[aria-pressed="false"]').trigger('click');
        expect(wrapper.text()).toContain('meridian/deployment');
        expect(wrapper.text()).toContain('Deployment automation');
        expect(wrapper.text()).toContain('5');
        expect(wrapper.text()).not.toContain('meridian/frontend');

        const repositoryButton = wrapper
            .findAll('button')
            .find((button) => button.text().includes('meridian/deployment'));
        if (!repositoryButton) throw new Error('Repository button not found');
        await repositoryButton.trigger('click');
        expect(wrapper.emitted('select')).toEqual([[gitlabRepo]]);
        wrapper.unmount();
    });

    it('distinguishes loading, empty, provider-empty, and search-empty states', async () => {
        stubs.loading = true;
        const loadingWrapper = await mountPicker();
        expect(loadingWrapper.get('[role="status"]').text()).toBe('Loading repositories…');
        loadingWrapper.unmount();

        stubs.loading = false;
        stubs.repositoryValues = [];
        const emptyWrapper = await mountPicker();
        await flushPromises();
        expect(emptyWrapper.text()).toContain('No repositories available.');
        emptyWrapper.unmount();

        stubs.repositoryValues = [githubRepo];
        const filteredWrapper = await mountPicker();
        await flushPromises();
        await filteredWrapper.get('button[aria-pressed="false"]').trigger('click');
        expect(filteredWrapper.text()).toContain('No repositories available for GitLab.');
        await filteredWrapper.get('input[aria-label="Search repositories…"]').setValue('missing');
        expect(filteredWrapper.text()).toContain('No repositories match your search.');
        filteredWrapper.unmount();
    });

    it('shows fetch errors above empty states and retries through the repository store', async () => {
        stubs.repositoryValues = [];
        stubs.fetchRepositories.mockRejectedValueOnce(new Error('unavailable'));
        const wrapper = await mountPicker();
        await flushPromises();

        expect(wrapper.get('[role="alert"]').text()).toContain('Unable to load repositories.');
        expect(wrapper.text()).not.toContain('No repositories available.');
        expect(stubs.error).toHaveBeenCalledWith('Failed to fetch repositories');

        stubs.fetchRepositories.mockResolvedValueOnce([]);
        await wrapper.get('[role="alert"] button').trigger('click');
        await flushPromises();
        expect(stubs.fetchRepositories).toHaveBeenCalledTimes(2);
        expect(wrapper.find('[role="alert"]').exists()).toBe(false);
        expect(wrapper.text()).toContain('No repositories available.');
        wrapper.unmount();
    });
});
