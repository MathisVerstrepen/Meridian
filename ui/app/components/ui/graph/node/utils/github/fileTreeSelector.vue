<script lang="ts" setup>
import type { FileTreeNode, RepositoryInfo, GithubCommitState, RepoContent } from '@/types/github';

// --- Props ---
const props = defineProps<{
    treeData: FileTreeNode;
    initialSelectedPaths?: FileTreeNode[];
    repo: RepositoryInfo;
    branches: string[];
    initialBranch: string;
}>();

// --- Emits ---
const emit = defineEmits(['update:selectedFiles', 'update:repoContent', 'close']);

// --- Plugins ---
const { $markedWorker } = useNuxtApp();

// --- Composables ---
const { getGenericRepoFile, getGenericRepoTree, getRepoCommitState, pullGenericRepo } = useAPI();
const { getIconForFile } = useFileIcons();
const { success } = useToast();

// --- State ---
const searchQuery = ref('');
const expandedPaths = ref<Set<string>>(new Set(['.'])); // Start with root expanded
const selectedPaths = ref<Set<FileTreeNode>>(new Set(props.initialSelectedPaths || []));
const selectPreview = ref<FileTreeNode | null>(null);
const previewHtml = ref<string | null>(null);
const isPulling = ref(false);
const isCommitStateLoading = ref(false);
const commitState = ref<GithubCommitState | null>(null);
const currentBranch = ref(props.initialBranch);
const AUTO_EXPAND_SEARCH_THRESHOLD = 2;
const isSearching = ref(false);
const searchDebounceTimer = ref<number | null>(null);
const filteredTreeData = ref<FileTreeNode | null>(props.treeData);
const regexCache = ref<Map<string, RegExp | null>>(new Map());
const warnedPatterns = ref<Set<string>>(new Set());

// --- Helper Functions ---

const parseSearchPatterns = (query: string): string[] => {
    return query
        .split(',')
        .map((pattern) => pattern.trim())
        .filter((pattern) => pattern.length > 0);
};

const isRegexPattern = (pattern: string): boolean => {
    const regexMetacharacters = /[.+^${}()|[\]\\]/;
    return regexMetacharacters.test(pattern) || (pattern.startsWith('/') && pattern.endsWith('/'));
};

const isWildcardPattern = (pattern: string): boolean => {
    return pattern.includes('*') || pattern.includes('?');
};

const createRegexFromPattern = (pattern: string): RegExp | null => {
    // Check cache first
    if (regexCache.value.has(pattern)) {
        return regexCache.value.get(pattern);
    }

    try {
        let regex: RegExp | null = null;

        // Explicit regex patterns wrapped in forward slashes
        if (pattern.startsWith('/') && pattern.endsWith('/')) {
            const regexPattern = pattern.slice(1, -1);
            regex = new RegExp(regexPattern, 'i');
        }
        // Wildcard patterns
        else if (isWildcardPattern(pattern)) {
            const escapedPattern = pattern
                .replace(/[.+^${}()|[\]\\]/g, '\\$&')
                .replace(/\*/g, '.*')
                .replace(/\?/g, '.');
            regex = new RegExp(`^${escapedPattern}$`, 'i');
        }
        // Explicit regex patterns (without slashes)
        else if (isRegexPattern(pattern)) {
            regex = new RegExp(pattern, 'i');
        }

        regexCache.value.set(pattern, regex);
        return regex;
    } catch (error) {
        if (!warnedPatterns.value.has(pattern)) {
            console.warn(`Invalid regex pattern: ${pattern}`, error);
            warnedPatterns.value.add(pattern);
        }

        regexCache.value.set(pattern, null); // Prevent re-compute
        return null;
    }
};

const matchesPattern = (filename: string, pattern: string): boolean => {
    const regex = createRegexFromPattern(pattern);

    if (regex) {
        return regex.test(filename);
    }

    // Fallback to substring match
    return filename.toLowerCase().includes(pattern.toLowerCase());
};

const matchesAnyPattern = (filename: string, patterns: string[]): boolean => {
    return patterns.some((pattern) => matchesPattern(filename, pattern));
};

const clearRegexCache = () => {
    regexCache.value.clear();
    warnedPatterns.value.clear();
};

const getAllDescendantFiles = (node: FileTreeNode): FileTreeNode[] => {
    if (node.type === 'file') {
        return [node];
    }
    if (!node.children || node.children.length === 0) {
        return [];
    }
    return node.children.flatMap(getAllDescendantFiles);
};

const getAllDirectoryPaths = (node: FileTreeNode): string[] => {
    let paths: string[] = [];
    if (node.type === 'directory') {
        paths.push(node.path);
        if (node.children) {
            paths = paths.concat(...node.children.map(getAllDirectoryPaths));
        }
    }
    return paths;
};

const selectPreviewIcon = computed(() => {
    if (!selectPreview.value) return 'MdiFileOutline';
    const fileIcon = getIconForFile(selectPreview.value.name);
    return fileIcon ? `fileTree/${fileIcon}` : 'MdiFileOutline';
});

// --- Methods ---
const toggleExpand = (path: string) => {
    if (expandedPaths.value.has(path)) {
        expandedPaths.value.delete(path);
    } else {
        expandedPaths.value.add(path);
    }
};

const toggleSelect = (node: FileTreeNode) => {
    if (node.type === 'file') {
        const existingNode = [...selectedPaths.value].find((item) => item.path === node.path);
        if (existingNode) {
            selectedPaths.value.delete(existingNode);
        } else {
            const nodeCopy = { ...node };
            delete nodeCopy.children;
            selectedPaths.value.add(nodeCopy);
        }
    } else if (node.type === 'directory') {
        const descendantFiles = getAllDescendantFiles(node);
        if (descendantFiles.length === 0) return;

        const descendantFilePaths = new Set(descendantFiles.map((f) => f.path));
        const currentlySelectedInDir = [...selectedPaths.value].filter((sf) =>
            descendantFilePaths.has(sf.path),
        );

        // If not all files are selected (indeterminate or none), select all.
        if (currentlySelectedInDir.length < descendantFiles.length) {
            descendantFiles.forEach((file) => {
                if (![...selectedPaths.value].some((sf) => sf.path === file.path)) {
                    const fileCopy = { ...file };
                    delete fileCopy.children;
                    selectedPaths.value.add(fileCopy);
                }
            });
        }
        // If all files are selected, deselect all.
        else {
            const newSelectedPaths = new Set(
                [...selectedPaths.value].filter(
                    (selectedFile) => !descendantFilePaths.has(selectedFile.path),
                ),
            );
            selectedPaths.value = newSelectedPaths;
        }
    }

    emit('update:selectedFiles', Array.from(selectedPaths.value));
};

const confirmSelection = () => {
    emit('close', {
        files: Array.from(selectedPaths.value),
        branch: currentBranch.value,
    });
};

const parseContent = async (markdown: string) => {
    previewHtml.value = await $markedWorker.parse(markdown);
};

const filenameToCode = (filename: string, content: string) => {
    const fileext = filename.split('.').pop();
    return `\`\`\`${fileext}\n${content}\n\`\`\``;
};

const expandAll = () => {
    if (!props.treeData) return;
    const allPaths = getAllDirectoryPaths(props.treeData);
    expandedPaths.value = new Set(allPaths);
};

const collapseAll = () => {
    expandedPaths.value = new Set(['.']);
};

const pullLatestChanges = async () => {
    isPulling.value = true;
    const { encoded_provider, full_name } = props.repo;
    const [owner, repoName] = full_name.split('/');
    try {
        await pullGenericRepo(encoded_provider, owner, repoName, currentBranch.value);

        const fileTree = await getGenericRepoTree(
            encoded_provider,
            owner,
            repoName,
            currentBranch.value,
        );

        if (fileTree) {
            filteredTreeData.value = fileTree;
            const newRepoContent: RepoContent = {
                repo: props.repo,
                currentBranch: currentBranch.value,
                selectedFiles: Array.from(selectedPaths.value),
            };
            emit('update:repoContent', newRepoContent, fileTree, props.branches);
            success('Successfully pulled latest changes.');
            await getCommitState();
        }
    } catch (error) {
        console.error('Failed to pull latest changes:', error);
    } finally {
        isPulling.value = false;
    }
};

const getCommitState = async () => {
    if (props.repo.provider !== 'github') {
        commitState.value = null;
        return;
    }
    isCommitStateLoading.value = true;
    const [owner, repoName] = props.repo.full_name.split('/');
    commitState.value = await getRepoCommitState(owner, repoName, currentBranch.value);
    isCommitStateLoading.value = false;
};

// --- Watchers ---
watch(selectPreview, async (newPreview) => {
    if (newPreview && newPreview.type === 'file' && newPreview) {
        const { encoded_provider, full_name } = props.repo;
        const [owner, repoName] = full_name.split('/');
        const content = await getGenericRepoFile(
            encoded_provider,
            owner,
            repoName,
            newPreview.path,
            currentBranch.value,
        );
        if (!content?.content) {
            previewHtml.value =
                '<p class="text-stone-gray/40">Could not load preview for this file.</p>';
            return;
        }
        await parseContent(filenameToCode(newPreview.name, content.content));
    } else {
        previewHtml.value = null;
    }
});

watch(currentBranch, async (newBranch, oldBranch) => {
    if (!newBranch || newBranch === oldBranch) return;
    isPulling.value = true;
    const { encoded_provider, full_name } = props.repo;
    const [owner, repoName] = full_name.split('/');
    try {
        const fileTree = await getGenericRepoTree(encoded_provider, owner, repoName, newBranch);
        if (fileTree) {
            filteredTreeData.value = fileTree;
            const newRepoContent: RepoContent = {
                repo: props.repo,
                currentBranch: newBranch,
                selectedFiles: [],
            };
            emit('update:repoContent', newRepoContent, fileTree, props.branches);
            selectedPaths.value.clear();
            emit('update:selectedFiles', []);
            await getCommitState();
        }
    } catch (error) {
        console.error(`Failed to load tree for branch ${newBranch}:`, error);
    } finally {
        isPulling.value = false;
    }
});

watch(searchQuery, (newQuery) => {
    if (searchDebounceTimer.value) {
        clearTimeout(searchDebounceTimer.value);
    }
    isSearching.value = true;

    searchDebounceTimer.value = window.setTimeout(() => {
        if (!newQuery) {
            filteredTreeData.value = props.treeData;
            isSearching.value = false;
            collapseAll();
            clearRegexCache(); // Clear cache when search is cleared
            return;
        }

        const searchPatterns = parseSearchPatterns(newQuery);

        const filterNodes = (node: FileTreeNode): FileTreeNode | null => {
            if (matchesAnyPattern(node.path, searchPatterns)) {
                return { ...node };
            }
            if (node.children && node.children.length > 0) {
                const filteredChildren = node.children
                    .map(filterNodes)
                    .filter(Boolean) as FileTreeNode[];
                if (filteredChildren.length > 0) {
                    return { ...node, children: filteredChildren };
                }
            }
            return null;
        };

        filteredTreeData.value = filterNodes(props.treeData);
        isSearching.value = false;

        if (newQuery.length > AUTO_EXPAND_SEARCH_THRESHOLD && filteredTreeData.value) {
            const allVisibleDirPaths = getAllDirectoryPaths(filteredTreeData.value);
            expandedPaths.value = new Set(allVisibleDirPaths);
        }
    }, 250);
});

onMounted(async () => {
    await getCommitState();
});

onUnmounted(() => {
    if (searchDebounceTimer.value) {
        clearTimeout(searchDebounceTimer.value);
    }
    clearRegexCache(); // Clear cache on component unmount
});
</script>

<template>
    <div class="flex h-full w-1/2 shrink-0 flex-col">
        <!-- Header -->
        <div class="border-stone-gray/20 mb-4 flex items-center justify-between border-b pb-4">
            <div class="flex items-center gap-2">
                <UiIcon
                    :name="repo.provider?.startsWith('gitlab') ? 'MdiGitlab' : 'MdiGithub'"
                    class="text-soft-silk h-6 w-6"
                />
                <h2 class="text-soft-silk text-xl font-bold">Select Files</h2>
                <span class="text-stone-gray/40 ml-2 translate-y-0.5 text-sm">from</span>
                <a
                    :href="repo.clone_url_https"
                    target="_blank"
                    class="text-soft-silk/80 hover:text-soft-silk translate-y-0.5 text-sm
                        underline-offset-2 duration-200 ease-in-out hover:underline"
                >
                    {{ repo.full_name }}
                </a>
            </div>
        </div>

        <!-- Branch Selector & Search -->
        <div class="mb-4 flex gap-2">
            <UiGraphNodeUtilsGithubBranchSelect
                v-model:current-branch="currentBranch"
                :branches="branches"
            />
            <div class="relative grow">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/60 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
                />
                <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="Search files... (wildcards: *.js, regex: /^test.*\.js$/i)"
                    class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow
                        w-full rounded-lg border px-10 py-2 focus:outline-none"
                />
                <button
                    v-if="searchQuery"
                    class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 absolute
                        top-1/2 right-3 flex h-6 w-6 -translate-y-1/2 cursor-pointer items-center
                        justify-center rounded-lg transition-colors"
                    @click="searchQuery = ''"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                </button>
            </div>
        </div>

        <!-- Breadcrumb & Actions -->
        <div class="mb-3 flex items-center justify-between">
            <div class="flex items-center gap-1 text-sm">
                <span v-if="commitState" class="text-stone-gray/60 flex items-center gap-1">
                    <UiIcon name="MdiSourceCommit" class="h-4 w-4" />
                    <a
                        :href="`https://github.com/${repo.full_name}/tree/${commitState?.latest_local.hash}`"
                        about="View this commit on GitHub"
                        target="_blank"
                        class="text-stone-gray/60 hover:text-soft-silk/80 underline-offset-2
                            duration-200 ease-in-out hover:underline"
                        >{{ commitState?.latest_local.hash.slice(0, 7) }}</a
                    >
                </span>
            </div>
            <div class="flex items-center gap-1">
                <button
                    title="Expand All"
                    class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 rounded-md
                        px-2 py-1 transition-colors"
                    @click="expandAll"
                >
                    <UiIcon name="MdiExpandAllOutline" class="h-4 w-4" />
                </button>
                <button
                    title="Collapse All"
                    class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 rounded-md
                        px-2 py-1 transition-colors"
                    @click="collapseAll"
                >
                    <UiIcon name="MdiCollapseAllOutline" class="h-4 w-4" />
                </button>
                <button
                    v-if="repo.provider === 'github'"
                    title="Pull Latest Changes"
                    class="disabled:hover:bg-stone-gray/10 flex cursor-pointer items-center gap-1
                        rounded-md px-2.5 py-1.5 text-sm transition-colors
                        disabled:cursor-not-allowed disabled:opacity-50"
                    :class="{
                        [`bg-ember-glow/20 text-ember-glow/80 hover:bg-ember-glow/30
                        hover:text-ember-glow/100`]: !commitState?.is_up_to_date,
                        [`text-stone-gray/60 hover:text-soft-silk/80 bg-stone-gray/10
                        hover:bg-stone-gray/20`]: !commitState || commitState?.is_up_to_date,
                    }"
                    :disabled="isPulling || isCommitStateLoading || commitState?.is_up_to_date"
                    @click="pullLatestChanges"
                >
                    <UiIcon
                        v-if="!commitState?.is_up_to_date || isCommitStateLoading || isPulling"
                        name="MaterialSymbolsChangeCircleRounded"
                        class="h-4 w-4"
                        :class="{ 'animate-spin': isPulling || isCommitStateLoading }"
                    />
                    <p v-if="isPulling">Loading...</p>
                    <p v-else-if="isCommitStateLoading">Checking status...</p>
                    <p v-else-if="!commitState?.is_up_to_date">Pull latest changes</p>
                    <p v-else>Up to date</p>
                </button>
            </div>
        </div>

        <!-- File Tree -->
        <div
            class="bg-obsidian/50 border-stone-gray/20 dark-scrollbar flex-grow overflow-y-auto
                rounded-lg border"
        >
            <UiGraphNodeUtilsGithubFileTreeNode
                v-if="filteredTreeData"
                :node="filteredTreeData"
                :level="0"
                :expanded-paths="expandedPaths"
                :selected-paths="Array.from(selectedPaths).map((node) => node.path)"
                @toggle-expand="toggleExpand"
                @toggle-select="toggleSelect"
                @toggle-select-preview="(node) => (selectPreview = node)"
            />
            <!-- No results found -->
            <div v-else-if="!isSearching && searchQuery" class="text-stone-gray/40 p-4 text-center">
                No files found matching your search.
            </div>
        </div>

        <!-- Actions -->
        <div class="mt-4 flex justify-end gap-3">
            <button
                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk cursor-pointer
                    rounded-lg px-4 py-2 transition-colors duration-200 ease-in-out"
                @click="$emit('close')"
            >
                Cancel
            </button>
            <button
                class="bg-ember-glow text-soft-silk cursor-pointer rounded-lg px-4 py-2
                    transition-colors duration-200 ease-in-out hover:brightness-90"
                :disabled="selectedPaths.size === 0"
                :class="{ '!cursor-not-allowed !opacity-50': selectedPaths.size === 0 }"
                @click="confirmSelection"
            >
                Confirm Selection ({{ selectedPaths.size }})
            </button>
        </div>
    </div>

    <div
        class="bg-obsidian/50 border-stone-gray/20 mx-4 flex h-full grow overflow-hidden rounded-lg
            border p-4"
    >
        <p v-if="!selectPreview" class="text-stone-gray/40">
            Please select a file to see a preview.
        </p>
        <div v-else class="flex h-full w-full flex-col gap-4 overflow-hidden">
            <div class="text-stone-gray/60 bg-stone-gray/10 rounded-lg p-2 px-4 font-mono text-sm">
                <UiIcon
                    :name="selectPreviewIcon"
                    class="h-4 w-4 text-transparent"
                    :class="{
                        '!text-stone-gray/70': selectPreviewIcon === 'MdiFileOutline',
                    }"
                />
                {{ selectPreview.path }}
            </div>
            <div class="file-preview dark-scrollbar grow overflow-y-auto" v-html="previewHtml" />
        </div>
    </div>
</template>
