import type { GithubSelectorTab } from '@/composables/useGraphEvents';
import type { RepoContent } from '@/types/github';

export const useChatGithubContext = () => {
    const graphEvents = useGraphEvents();
    const githubContext = ref<RepoContent | null>(null);

    const normalizeContext = (context: RepoContent | null) => {
        if (!context) return null;
        if (context.selectedFiles.length === 0 && (context.selectedIssues?.length ?? 0) === 0) {
            return null;
        }
        return context;
    };

    const openGithubContext = (initialTab: GithubSelectorTab) => {
        graphEvents.emit('open-github-file-select', {
            target: { kind: 'chat-input' },
            repoContent: githubContext.value,
            initialTab,
        });
    };

    const removeGithubContext = () => {
        githubContext.value = null;
    };

    onMounted(() => {
        const unsubscribe = graphEvents.on('close-github-file-select', ({ target, repoContent }) => {
            if (target.kind !== 'chat-input') return;
            githubContext.value = normalizeContext(repoContent);
        });
        onUnmounted(unsubscribe);
    });

    return { githubContext, openGithubContext, removeGithubContext };
};
