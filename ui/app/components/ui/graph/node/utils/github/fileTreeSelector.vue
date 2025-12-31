<script lang="ts" setup>
import type { FileTreeNode, RepositoryInfo, GitCommitState, RepoContent } from '@/types/github';

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
const { getGenericRepoFile, getGenericRepoTree, getRepositoryCommitState, pullGenericRepo } =
    useAPI();
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
const commitState = ref<GitCommitState | null>(null);
const currentBranch = ref(props.initialBranch);
const AUTO_EXPAND_SEARCH_THRESHOLD = 2;
const isSearching = ref(false);
const searchDebounceTimer = ref<number | null>(null);
const filteredTreeData = ref<FileTreeNode | null>(props.treeData);
const regexCache = ref<Map<string, RegExp | null>>(new Map());
const warnedPatterns = ref<Set<string>>(new Set());

// --- Search Options State ---
const isRegexEnabled = ref(false);
const isCaseSensitive = ref(false);
const isShowSelectedOnly = ref(false);

// --- Helper Functions ---

const parseSearchPatterns = (query: string): string[] => {
    // If Regex is enabled, treat the entire query as a single pattern
    if (isRegexEnabled.value) {
        return [query];
    }
    return query
        .split(',')
        .map((pattern) => pattern.trim())
        .filter((pattern) => pattern.length > 0);
};

const isWildcardPattern = (pattern: string): boolean => {
    return pattern.includes('*') || pattern.includes('?');
};

const createRegexFromPattern = (pattern: string): RegExp | null => {
    // Cache key includes case sensitivity to prevent stale flags
    const cacheKey = `${pattern}_${isCaseSensitive.value}`;

    // Check cache first
    if (regexCache.value.has(cacheKey)) {
        return regexCache.value.get(cacheKey);
    }

    try {
        let regex: RegExp | null = null;
        const flags = isCaseSensitive.value ? '' : 'i';

        // Explicit regex patterns wrapped in forward slashes
        if (pattern.startsWith('/') && pattern.endsWith('/')) {
            const regexPattern = pattern.slice(1, -1);
            regex = new RegExp(regexPattern, flags);
        }
        // Wildcard patterns
        else if (isWildcardPattern(pattern) && !isRegexEnabled.value) {
            const escapedPattern = pattern
                .replace(/[.+^${}()|[\]\\]/g, '\\$&')
                .replace(/\*/g, '.*')
                .replace(/\?/g, '.');
            regex = new RegExp(`^${escapedPattern}$`, flags);
        }
        // Raw Regex
        else {
            regex = new RegExp(pattern, flags);
        }

        regexCache.value.set(cacheKey, regex);
        return regex;
    } catch (error) {
        if (!warnedPatterns.value.has(pattern)) {
            console.warn(`Invalid regex pattern: ${pattern}`, error);
            warnedPatterns.value.add(pattern);
        }

        regexCache.value.set(cacheKey, null); // Prevent re-compute
        return null;
    }
};

const matchesPattern = (filename: string, pattern: string): boolean => {
    // 1. Simple String Match (Regex Disabled)
    if (!isRegexEnabled.value) {
        if (isWildcardPattern(pattern)) {
            const regex = createRegexFromPattern(pattern);
            return regex ? regex.test(filename) : false;
        }

        if (isCaseSensitive.value) {
            return filename.includes(pattern);
        }
        return filename.toLowerCase().includes(pattern.toLowerCase());
    }

    // 2. Regex Mode (Regex Enabled)
    const regex = createRegexFromPattern(pattern);

    if (regex) {
        return regex.test(filename);
    }

    return false;
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

const performSearch = (query: string) => {
    if (!query && !isShowSelectedOnly.value) {
        filteredTreeData.value = props.treeData;
        isSearching.value = false;
        collapseAll();
        clearRegexCache();
        return;
    }

    const searchPatterns = parseSearchPatterns(query);
    const hasSearch = searchPatterns.length > 0;
    const showSelected = isShowSelectedOnly.value;

    if (showSelected) {
        // Strict Filter Mode: Show only selected items
        const strictFilter = (node: FileTreeNode): FileTreeNode | null => {
            if (node.type === 'file') {
                const isSelected = [...selectedPaths.value].some((s) => s.path === node.path);
                if (!isSelected) return null;
                if (hasSearch && !matchesAnyPattern(node.path, searchPatterns)) return null;
                return { ...node };
            }
            // Directory
            if (node.children) {
                const kids = node.children
                    .map(strictFilter)
                    .filter((n): n is FileTreeNode => n !== null);
                if (kids.length > 0) return { ...node, children: kids };
            }
            return null;
        };
        filteredTreeData.value = strictFilter(props.treeData);
    } else {
        // Standard Search Mode
        const searchFilter = (node: FileTreeNode): FileTreeNode | null => {
            if (matchesAnyPattern(node.path, searchPatterns)) {
                return { ...node };
            }
            if (node.children && node.children.length > 0) {
                const filteredChildren = node.children
                    .map(searchFilter)
                    .filter((n): n is FileTreeNode => n !== null);
                if (filteredChildren.length > 0) {
                    return { ...node, children: filteredChildren };
                }
            }
            return null;
        };
        filteredTreeData.value = searchFilter(props.treeData);
    }

    isSearching.value = false;

    if (filteredTreeData.value && (query.length > AUTO_EXPAND_SEARCH_THRESHOLD || showSelected)) {
        const allVisibleDirPaths = getAllDirectoryPaths(filteredTreeData.value);
        expandedPaths.value = new Set(allVisibleDirPaths);
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

    if (isShowSelectedOnly.value) {
        performSearch(searchQuery.value);
    }
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
    try {
        await pullGenericRepo(encoded_provider, full_name, currentBranch.value);

        const fileTree = await getGenericRepoTree(encoded_provider, full_name, currentBranch.value);

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
    isCommitStateLoading.value = true;
    commitState.value = await getRepositoryCommitState(
        props.repo.encoded_provider,
        props.repo.full_name,
        currentBranch.value,
    );
    isCommitStateLoading.value = false;
};

// --- Watchers ---
watch(selectPreview, async (newPreview) => {
    if (newPreview && newPreview.type === 'file' && newPreview) {
        // Check if image
        const isImage = /\.(png|jpe?g|gif|svg|webp|ico|bmp|tiff?)$/i.test(newPreview.name);

        if (isImage) {
            const { full_name, provider, clone_url_https } = props.repo;
            let rawUrl = '';

            if (provider === 'gitlab') {
                const baseUrl = clone_url_https.replace(/\.git$/, '');
                rawUrl = `${baseUrl}/-/raw/${currentBranch.value}/${newPreview.path.split('/').map(encodeURIComponent).join('/')}`;
            } else {
                rawUrl = `https://raw.githubusercontent.com/${full_name}/${currentBranch.value}/${newPreview.path.split('/').map(encodeURIComponent).join('/')}`;
            }

            previewHtml.value = `
                <div class="flex h-full w-full items-center justify-center overflow-hidden p-4">
                    <img 
                        src="${rawUrl}" 
                        alt="${newPreview.name}" 
                        class="max-h-full max-w-full rounded-lg border border-stone-gray/20 object-contain shadow-sm" 
                    />
                </div>`;
            return;
        }

        // Handle Text Files
        const { encoded_provider, full_name } = props.repo;
        const content = await getGenericRepoFile(
            encoded_provider,
            full_name,
            newPreview.path,
            currentBranch.value,
        );
        if (!content?.content) {
            previewHtml.value =
                '<p class="text-stone-gray/40 flex h-full w-full flex-col items-center justify-center text-center">Could not load preview for this file.</p>';
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
    try {
        const fileTree = await getGenericRepoTree(encoded_provider, full_name, newBranch);
        if (fileTree) {
            filteredTreeData.value = fileTree;
            const newRepoContent: RepoContent = {
                repo: props.repo,
                currentBranch: newBranch,
                selectedFiles: Array.from(selectedPaths.value),
            };
            emit('update:repoContent', newRepoContent, fileTree, props.branches);
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
        performSearch(newQuery);
    }, 250);
});

watch([isRegexEnabled, isCaseSensitive, isShowSelectedOnly], () => {
    // Save to local storage
    if (typeof window !== 'undefined') {
        localStorage.setItem('fileTreeSelector_isRegexEnabled', String(isRegexEnabled.value));
        localStorage.setItem('fileTreeSelector_isCaseSensitive', String(isCaseSensitive.value));
    }

    clearRegexCache();
    performSearch(searchQuery.value);
});

onMounted(async () => {
    if (typeof window !== 'undefined') {
        const savedRegex = localStorage.getItem('fileTreeSelector_isRegexEnabled');
        if (savedRegex !== null) isRegexEnabled.value = savedRegex === 'true';

        const savedCase = localStorage.getItem('fileTreeSelector_isCaseSensitive');
        if (savedCase !== null) isCaseSensitive.value = savedCase === 'true';
    }

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
            <div class="group relative grow">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/60 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
                />
                <input
                    v-model="searchQuery"
                    type="text"
                    :placeholder="
                        isRegexEnabled ? 'Regex search... (e.g. ^src/.*\\.vue$)' : 'Search files...'
                    "
                    class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow
                        w-full rounded-lg border py-2 pr-28 pl-10 transition-colors
                        focus:outline-none"
                />

                <!-- Search Options -->
                <div class="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-1">
                    <!-- Case Sensitive Toggle -->
                    <button
                        class="flex h-6 w-6 items-center justify-center rounded-md
                            transition-colors"
                        :class="
                            isCaseSensitive
                                ? 'bg-ember-glow/20 text-ember-glow'
                                : 'text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5'
                        "
                        title="Match Case"
                        @click="isCaseSensitive = !isCaseSensitive"
                    >
                        <UiIcon name="MdiFormatLetterCase" class="h-4 w-4" />
                    </button>

                    <!-- Regex Toggle -->
                    <button
                        class="flex h-6 w-6 items-center justify-center rounded-md
                            transition-colors"
                        :class="
                            isRegexEnabled
                                ? 'bg-ember-glow/20 text-ember-glow'
                                : 'text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5'
                        "
                        title="Use Regular Expression"
                        @click="isRegexEnabled = !isRegexEnabled"
                    >
                        <UiIcon name="MdiRegex" class="h-4 w-4" />
                    </button>

                    <!-- Clear Button -->
                    <button
                        v-if="searchQuery"
                        class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 flex h-6
                            w-6 cursor-pointer items-center justify-center rounded-md
                            transition-colors"
                        title="Clear Search"
                        @click="searchQuery = ''"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                    </button>
                </div>
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
                    title="Show Selected Only"
                    class="cursor-pointer items-center justify-center rounded-md px-2 py-1
                        transition-colors"
                    :class="
                        isShowSelectedOnly
                            ? 'bg-ember-glow/20 text-ember-glow'
                            : 'text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5'
                    "
                    @click="isShowSelectedOnly = !isShowSelectedOnly"
                >
                    <UiIcon
                        :name="isShowSelectedOnly ? 'MdiFilter' : 'MdiFilterOutline'"
                        class="h-4 w-4"
                    />
                </button>
                <div class="bg-stone-gray/20 mx-1 h-4 w-px" />
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
            <div
                v-else-if="isShowSelectedOnly && selectedPaths.size === 0"
                class="text-stone-gray/40 flex h-full items-center justify-center p-4 text-center"
            >
                No files selected.
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
        <div
            v-if="!selectPreview"
            class="text-stone-gray/40 flex h-full w-full flex-col items-center justify-center
                text-center"
        >
            <UiIcon name="MdiFileDocumentOutline" class="mb-4 h-12 w-12" />
            <p class="text-lg">No file selected</p>
            <p class="text-sm">Select a file from the tree to preview its content here.</p>
        </div>
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
