import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, h } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FileSelectMountpoint from '@/components/ui/graph/node/utils/github/fileSelectMountpoint.vue';
import type { RepoContent, RepositoryInfo } from '@/types/github';

const stubs = vi.hoisted(() => ({
    graphOn: vi.fn(),
    graphEmit: vi.fn(),
    fetchRepositories: vi.fn().mockResolvedValue([]),
    getGenericRepoTree: vi.fn(),
    getGenericRepoBranches: vi.fn(),
    cloneRepository: vi.fn(),
    pullGenericRepo: vi.fn(),
    error: vi.fn(),
}));

mockNuxtImport('useSettingsStore', () => () => ({ storeKind: 'settings' }));
mockNuxtImport('useRepositoryStore', () => () => ({
    fetchRepositories: stubs.fetchRepositories,
}));
mockNuxtImport('storeToRefs', () => () => ({
    blockGithubSettings: { value: { autoPull: false } },
}));
mockNuxtImport('useAPI', () => () => ({
    getGenericRepoTree: stubs.getGenericRepoTree,
    getGenericRepoBranches: stubs.getGenericRepoBranches,
    cloneRepository: stubs.cloneRepository,
    pullGenericRepo: stubs.pullGenericRepo,
}));
mockNuxtImport('useGraphEvents', () => () => ({ on: stubs.graphOn, emit: stubs.graphEmit }));
mockNuxtImport('useToast', () => () => ({ error: stubs.error }));

const RepoSelectStub = defineComponent({
    name: 'UiGraphNodeUtilsGithubRepoSelect',
    props: ['currentRepo'],
    emits: ['update:currentRepo'],
    setup: () => () => h('div', { 'data-repo-select': '' }),
});

const IssueSelectorStub = defineComponent({
    name: 'UiGraphNodeUtilsGithubIssuePrSelector',
    props: ['repo', 'initialSelectedIssues'],
    emits: ['update:selectedIssues', 'close'],
    setup: () => () => h('div', { 'data-issue-selector': '' }),
});

const SlotStub = defineComponent({
    setup(_, { slots }) {
        return () => h('div', slots.default?.());
    },
});

const repo: RepositoryInfo = {
    provider: 'github',
    encoded_provider: 'github',
    full_name: 'meridian/test',
    description: null,
    clone_url_ssh: 'git@example.test:meridian/test.git',
    clone_url_https: 'https://example.test/meridian/test.git',
    default_branch: 'develop',
};

const openHandler = () => {
    const registration = stubs.graphOn.mock.calls.find(
        (call) => call[0] === 'open-github-file-select',
    );
    if (!registration) throw new Error('Open handler was not registered');
    return registration[1];
};

const mountSelector = () =>
    mountSuspended(FileSelectMountpoint, {
        global: {
            stubs: {
                AnimatePresence: SlotStub,
                UiIcon: true,
                UiGraphNodeUtilsGithubRepoSelect: RepoSelectStub,
                UiGraphNodeUtilsGithubIssuePrSelector: IssueSelectorStub,
                UiGraphNodeUtilsGithubFileTreeSelector: true,
            },
        },
    });

describe('Git file selector mountpoint', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        stubs.graphOn.mockReturnValue(() => undefined);
        stubs.fetchRepositories.mockResolvedValue([]);
        stubs.getGenericRepoTree.mockResolvedValue({
            name: '.',
            type: 'directory',
            path: '.',
            children: [],
        });
        stubs.getGenericRepoBranches.mockResolvedValue(['develop']);
    });

    it('starts with repository selection and opens requested issues tab with default branch', async () => {
        const wrapper = await mountSelector();
        await openHandler()({
            target: { kind: 'chat-input' },
            repoContent: null,
            initialTab: 'issues',
        });
        await flushPromises();

        expect(stubs.fetchRepositories).toHaveBeenCalledOnce();
        const repoSelector = wrapper.getComponent(RepoSelectStub);
        repoSelector.vm.$emit('update:currentRepo', repo);
        await flushPromises();

        expect(wrapper.find('[data-issue-selector]').exists()).toBe(true);
        expect(stubs.getGenericRepoTree).toHaveBeenCalledWith('github', 'meridian/test', 'develop');

        wrapper.getComponent(IssueSelectorStub).vm.$emit('close', []);
        expect(stubs.graphEmit).toHaveBeenCalledWith('close-github-file-select', {
            target: { kind: 'chat-input' },
            repoContent: {
                repo,
                selectedFiles: [],
                selectedIssues: [],
                currentBranch: 'develop',
            },
        });
        wrapper.unmount();
    });

    it('returns the initial snapshot on close and preserves node target isolation', async () => {
        const wrapper = await mountSelector();
        const initial: RepoContent = {
            repo,
            selectedFiles: [
                { name: 'README.md', type: 'file', path: 'README.md', children: [] },
            ],
            selectedIssues: [],
            currentBranch: 'develop',
        };
        await openHandler()({
            target: { kind: 'node', nodeId: 'github-node' },
            repoContent: initial,
            initialTab: 'issues',
        });
        await flushPromises();

        await wrapper.get('button[aria-label="Close Fullscreen"]').trigger('click');
        expect(stubs.graphEmit).toHaveBeenCalledWith('close-github-file-select', {
            target: { kind: 'node', nodeId: 'github-node' },
            repoContent: initial,
        });
        wrapper.unmount();
    });
});
