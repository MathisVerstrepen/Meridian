import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { defineComponent, h, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HomePage from '@/pages/index.vue';
import type { ChatInputSubmission } from '@/types/chat';

const stubs = vi.hoisted(() => ({
    addMessage: vi.fn(),
    createGraph: vi.fn(),
    fetchData: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('motion-v', () => ({
    useSpring: (initial: number) => {
        let value = initial;
        return {
            on: vi.fn(),
            get: () => value,
            set: (next: number) => {
                value = next;
            },
        };
    },
}));

mockNuxtImport('useChatStore', () => () => ({
    storeKind: 'chat',
    resetChatState: vi.fn(),
    addMessage: stubs.addMessage,
    syncUpcomingModelDefaults: vi.fn(),
}));
mockNuxtImport('useSettingsStore', () => () => ({ storeKind: 'settings' }));
mockNuxtImport('storeToRefs', () => (store: { storeKind: string }) =>
    store.storeKind === 'chat'
        ? {
              openChatId: ref(null),
              upcomingModelData: ref({ data: {} }),
          }
        : {
              modelsSettings: ref({ defaultModel: 'test-model' }),
              toolsSettings: ref({ defaultAutoSelectTools: false, defaultSelectedTools: [] }),
              accountSettings: ref({ openRouterApiKey: 'key' }),
              isReady: ref(false),
          },
);
mockNuxtImport('useFiles', () => () => ({ fileToMessageContent: vi.fn() }));
mockNuxtImport('useAPI', () => () => ({
    createGraph: stubs.createGraph,
    moveGraph: vi.fn(),
}));
mockNuxtImport('useHistoryData', () => () => ({
    graphs: ref([]),
    folders: ref([]),
    workspaces: ref([]),
    hasMoreGraphs: ref(false),
    hasLoadedHistory: ref(true),
    fetchData: stubs.fetchData,
    fetchNextGraphsPage: vi.fn(),
}));
mockNuxtImport('useUniqueId', () => () => ({ generateId: () => 'generator-id' }));
mockNuxtImport('useUserSession', () => () => ({
    user: ref({ plan_type: 'pro', name: 'Test', has_seen_welcome: true }),
    loggedIn: ref(true),
    ready: ref(true),
    clear: vi.fn(),
    fetch: vi.fn(),
}));
mockNuxtImport('useToast', () => () => ({ error: vi.fn() }));
mockNuxtImport('useGraphDeletion', () => () => ({ handleDeleteGraph: vi.fn() }));

const TextInputStub = defineComponent({
    name: 'UiChatTextInput',
    emits: ['generate'],
    setup: () => () => h('div'),
});

describe('home chat input', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        stubs.fetchData.mockResolvedValue(undefined);
        stubs.createGraph.mockResolvedValue({
            id: 'graph-id',
            temporary: false,
            folder_id: null,
            workspace_id: null,
        });
    });

    it('persists Git context in initial message data before navigation', async () => {
        const wrapper = await mountSuspended(HomePage, {
            shallow: true,
            global: { stubs: { UiChatTextInput: TextInputStub } },
        });
        const submission: ChatInputSubmission = {
            message: 'Inspect repository',
            files: [],
            githubContext: {
                repo: {
                    provider: 'github',
                    encoded_provider: 'github',
                    full_name: 'meridian/test',
                    description: null,
                    clone_url_ssh: '',
                    clone_url_https: '',
                    default_branch: 'main',
                },
                selectedFiles: [
                    { name: 'README.md', type: 'file', path: 'README.md', children: [] },
                ],
                selectedIssues: [],
                currentBranch: 'main',
            },
        };

        wrapper.findComponent(TextInputStub).vm.$emit('generate', submission);
        await vi.waitFor(() => expect(stubs.addMessage).toHaveBeenCalledOnce());

        expect(stubs.addMessage.mock.calls[0]?.[0]).toMatchObject({
            data: {
                files: [],
                githubContext: submission.githubContext,
            },
        });
        wrapper.unmount();
    });
});
