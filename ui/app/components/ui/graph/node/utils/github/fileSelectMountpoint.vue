<script lang="ts" setup>
import { motion } from 'motion-v';
import type { RepoContent, FileTreeNode, GithubIssue } from '@/types/github';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { blockGithubSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { getGenericRepoTree, getGenericRepoBranches, cloneRepository, pullGenericRepo } = useAPI();
const graphEvents = useGraphEvents();
const { error } = useToast();

// --- Local State ---
const isOpen = ref(false);
const repoContent = ref<RepoContent | null>(null);
const selectedFiles = ref<FileTreeNode[]>([]);
const initialSelectedFiles = ref<FileTreeNode[]>([]);
const selectedIssues = ref<GithubIssue[]>([]);
const initialSelectedIssues = ref<GithubIssue[]>([]);
const activeNodeId = ref<string | null>(null);
const fileTree = ref<FileTreeNode>();
const branches = ref<string[]>([]);
const loadingState = ref(0); // 0: idle, 1: cloning, 2: fetching tree
const errorState = ref<string | null>(null);
const activeTab = ref<'files' | 'issues'>('files');

// --- Core Logic Functions ---
const fetchGithubData = async () => {
    if (!repoContent.value) return;

    loadingState.value = 2;

    const { provider, full_name, clone_url_ssh } = repoContent.value.repo;
    const encoded_provider =
        repoContent.value.repo.encoded_provider || btoa(unescape(encodeURIComponent('github')));

    // AutoPull on mount if enabled
    try {
        if (blockGithubSettings.value?.autoPull) {
            await pullGenericRepo(
                encoded_provider,
                full_name,
                repoContent.value.currentBranch,
                false,
            );
        }
    } catch (error) {
        console.warn('Auto-pull failed', error);
    }

    let fileTreeResponse;
    try {
        fileTreeResponse = await getGenericRepoTree(
            encoded_provider,
            full_name,
            repoContent.value.currentBranch,
        );
    } catch {
        loadingState.value = 1;
        if (provider === 'gitlab') {
            await cloneRepository(provider, full_name, clone_url_ssh, 'ssh');
        } else {
            await cloneRepository(
                provider,
                full_name,
                repoContent.value.repo.clone_url_https,
                'https',
            );
        }

        try {
            fileTreeResponse = await getGenericRepoTree(
                encoded_provider,
                full_name,
                repoContent.value.currentBranch,
            );
        } catch {
            error('Failed to fetch repository file tree');
            errorState.value =
                'Failed to fetch repository file tree. This may be due to the repository being empty.';
            return;
        }
    } finally {
        loadingState.value = 0;
    }

    fileTree.value = fileTreeResponse;

    const branchesResponse = await getGenericRepoBranches(encoded_provider, full_name);
    if (!branchesResponse) {
        error('Failed to fetch repository branches');
        errorState.value = 'Failed to fetch repository branches.';
        return;
    }
    branches.value = branchesResponse;
};

const closeFullscreen = (payload?: {
    files: FileTreeNode[];
    branch: string;
    issues: GithubIssue[];
}) => {
    graphEvents.emit('close-github-file-select', {
        selectedFilePaths: payload ? payload.files : initialSelectedFiles.value,
        selectedIssues: payload ? payload.issues : initialSelectedIssues.value,
        nodeId: activeNodeId.value || '',
        branch: payload ? payload.branch : repoContent.value?.currentBranch,
    });

    repoContent.value = null;
    isOpen.value = false;
    selectedFiles.value = [];
    selectedIssues.value = [];
    activeNodeId.value = null;
    fileTree.value = undefined;
    branches.value = [];
    activeTab.value = 'files';
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isOpen.value) {
        closeFullscreen();
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('open-github-file-select', async (payload) => {
        isOpen.value = true;
        repoContent.value = payload.repoContent;
        selectedFiles.value = payload.repoContent.selectedFiles || [];
        selectedIssues.value = payload.repoContent.selectedIssues || [];
        activeNodeId.value = payload.nodeId;
        initialSelectedFiles.value = [...selectedFiles.value];
        initialSelectedIssues.value = [...selectedIssues.value];
        errorState.value = null;

        // Gitlab migration support
        if (!repoContent.value.repo.provider) {
            repoContent.value.repo.provider = 'github';
        }
        if (!repoContent.value.repo.encoded_provider) {
            repoContent.value.repo.encoded_provider = btoa(unescape(encodeURIComponent('github')));
        }

        fetchGithubData();
    });

    document.addEventListener('keydown', handleKeyDown);

    onUnmounted(unsubscribe);
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-show="isOpen"
            id="github-file-select-mountpoint"
            key="github-file-select-mountpoint"
            :initial="{ opacity: 0, scale: 0.85 }"
            :animate="{ opacity: 1, scale: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
            :exit="{ opacity: 0, scale: 0.85, transition: { duration: 0.15, ease: 'easeIn' } }"
            class="bg-obsidian/90 border-stone-gray/10 absolute top-1/2 left-1/2 z-50 mx-auto flex
                h-[95%] w-[95%] -translate-x-1/2 -translate-y-1/2 cursor-grab flex-col
                overflow-hidden rounded-2xl border-2 shadow-lg backdrop-blur-md"
        >
            <!-- Close Button -->
            <button
                class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2.5 right-2.5 z-50 flex
                    h-10 w-10 items-center justify-center justify-self-end rounded-full
                    backdrop-blur-sm transition-colors duration-200 ease-in-out
                    hover:cursor-pointer"
                aria-label="Close Fullscreen"
                title="Close Fullscreen"
                @click="
                    closeFullscreen(
                        repoContent
                            ? {
                                  files: selectedFiles,
                                  branch: repoContent.currentBranch,
                                  issues: selectedIssues,
                              }
                            : undefined,
                    )
                "
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>

            <!-- Sidebar / Tabs -->
            <div class="flex h-full w-full">
                <!-- Tab Navigation (Left Side) -->
                <div
                    class="bg-obsidian/50 border-stone-gray/10 flex w-16 flex-col items-center gap-4
                        border-r py-8"
                >
                    <button
                        class="flex h-10 w-10 items-center justify-center rounded-lg transition-all
                            duration-200"
                        :class="
                            activeTab === 'files'
                                ? 'bg-ember-glow/20 text-ember-glow'
                                : 'text-stone-gray/60 hover:text-soft-silk hover:bg-stone-gray/10'
                        "
                        title="Files"
                        @click="activeTab = 'files'"
                    >
                        <UiIcon name="MdiFileDocumentOutline" class="h-6 w-6" />
                    </button>

                    <button
                        v-if="
                            repoContent?.repo.provider === 'github' ||
                            repoContent?.repo.provider === 'github'
                        "
                        class="flex h-10 w-10 items-center justify-center rounded-lg transition-all
                            duration-200"
                        :class="
                            activeTab === 'issues'
                                ? 'bg-ember-glow/20 text-ember-glow'
                                : 'text-stone-gray/60 hover:text-soft-silk hover:bg-stone-gray/10'
                        "
                        title="Issues & PRs"
                        @click="activeTab = 'issues'"
                    >
                        <UiIcon name="MdiSourcePull" class="h-6 w-6" />
                    </button>
                </div>

                <!-- Main Content -->
                <div class="flex grow overflow-hidden p-8">
                    <template v-if="repoContent && fileTree && activeTab === 'files'">
                        <UiGraphNodeUtilsGithubFileTreeSelector
                            :tree-data="fileTree"
                            :initial-selected-paths="selectedFiles"
                            :repo="repoContent.repo"
                            :branches="branches"
                            :initial-branch="repoContent.currentBranch"
                            @update:selected-files="selectedFiles = $event"
                            @update:repo-content="
                                (newRepoContent, newFileTree, newBranches) => {
                                    repoContent = newRepoContent;
                                    if (newFileTree) {
                                        fileTree = newFileTree;
                                    }
                                    if (newBranches) {
                                        branches = newBranches;
                                    }
                                }
                            "
                            @close="
                                (payload) =>
                                    closeFullscreen({
                                        files: payload.files,
                                        branch: payload.branch,
                                        issues: selectedIssues,
                                    })
                            "
                        />
                    </template>

                    <template v-else-if="repoContent && activeTab === 'issues'">
                        <UiGraphNodeUtilsGithubIssuePrSelector
                            :repo="repoContent.repo"
                            :initial-selected-issues="selectedIssues"
                            @update:selected-issues="selectedIssues = $event"
                            @close="
                                closeFullscreen({
                                    files: selectedFiles,
                                    branch: repoContent.currentBranch,
                                    issues: selectedIssues,
                                })
                            "
                        />
                    </template>

                    <div
                        v-else-if="!repoContent || !fileTree"
                        class="text-stone-gray/50 m-auto flex flex-col items-center gap-4
                            text-center text-sm"
                    >
                        <template v-if="loadingState === 1">
                            <UiIcon name="MingcuteLoading3Fill" class="h-6 w-6 animate-spin" />
                            <span>
                                Preparing repository... <br />
                                <span class="text-stone-gray/25"
                                    >This may take a few seconds for the initial clone.</span
                                >
                            </span>
                        </template>

                        <template v-if="loadingState === 2">
                            <UiIcon name="MdiGithub" class="h-6 w-6" />
                            <span>
                                Loading repository structure... <br />
                                <span class="text-stone-gray/25"
                                    >This may take a few seconds depending on the size of the
                                    repository and is auto-pulling is enabled.</span
                                >
                            </span>
                        </template>

                        <template v-else-if="errorState">
                            <UiIcon
                                name="MaterialSymbolsErrorCircleRounded"
                                class="h-6 w-6 text-red-500"
                            />
                            <span class="text-red-500">
                                {{ errorState }} <br />
                                <span class="text-red-500/50"
                                    >Please ensure the repository is not empty and try again.</span
                                >
                            </span>
                        </template>
                    </div>
                </div>
            </div>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
