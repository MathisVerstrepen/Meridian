<script lang="ts" setup>
import type { FileTreeNode, Repo } from '@/types/github';

// --- Props ---
const props = defineProps<{
    treeData: FileTreeNode;
    initialSelectedPaths?: FileTreeNode[];
    repo: Repo;
}>();

// --- Emits ---
const emit = defineEmits(['update:selectedFiles', 'close']);

// --- Plugins ---
const { $markedWorker } = useNuxtApp();

// --- Composables ---
const { getRepoFile } = useAPI();
const { getIconForFile } = useFileIcons();

// --- State ---
const searchQuery = ref('');
const expandedPaths = ref<Set<string>>(new Set(['.'])); // Start with root expanded
const selectedPaths = ref<Set<FileTreeNode>>(new Set(props.initialSelectedPaths || []));
const breadcrumb = ref<string[]>(['root']);
const selectPreview = ref<FileTreeNode | null>(null);
const previewHtml = ref<string | null>(null);
const AUTO_EXPAND_SEARCH_THRESHOLD = 2;

// --- Helper Functions ---
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

// --- Computed ---
const filteredTree = computed(() => {
    if (!searchQuery.value) return props.treeData;

    const filterNodes = (node: FileTreeNode): FileTreeNode | null => {
        // If node matches search, include it and all its children
        if (node.name.toLowerCase().includes(searchQuery.value.toLowerCase())) {
            return { ...node };
        }

        // If it's a directory with children, filter them
        if (node.children && node.children.length > 0) {
            const filteredChildren = node.children
                .map(filterNodes)
                .filter(Boolean) as FileTreeNode[];

            if (filteredChildren.length > 0) {
                return {
                    ...node,
                    children: filteredChildren,
                };
            }
        }

        return null;
    };

    return filterNodes(props.treeData);
});

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

const navigateToPath = (pathParts: string[]) => {
    breadcrumb.value = ['root', ...pathParts];
};

const confirmSelection = () => {
    emit('close', Array.from(selectedPaths.value));
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

// --- Watchers ---
watch(selectPreview, async (newPreview) => {
    if (newPreview && newPreview.type === 'file' && newPreview) {
        const [owner, repoName] = props.repo.full_name.split('/');
        const content = await getRepoFile(owner, repoName, newPreview.path);
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

watch(searchQuery, (newQuery) => {
    if (newQuery.length > AUTO_EXPAND_SEARCH_THRESHOLD) {
        if (filteredTree.value) {
            const allVisibleDirPaths = getAllDirectoryPaths(filteredTree.value);
            expandedPaths.value = new Set(allVisibleDirPaths);
        }
    } else if (newQuery.length === 0) {
        collapseAll();
    }
});
</script>

<template>
    <div class="flex h-full w-1/2 shrink-0 flex-col">
        <!-- Header -->
        <div class="border-stone-gray/20 mb-4 flex items-center justify-between border-b pb-4">
            <h2 class="text-soft-silk text-xl font-bold">Select Files</h2>
        </div>

        <!-- Search -->
        <div class="relative mb-4">
            <UiIcon
                name="MdiMagnify"
                class="text-stone-gray/60 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
            />
            <input
                v-model="searchQuery"
                type="text"
                placeholder="Search files..."
                class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow w-full rounded-lg border
                    px-10 py-2 focus:outline-none"
            />
            <button
                v-if="searchQuery"
                @click="searchQuery = ''"
                class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 absolute top-1/2 right-3 flex h-6 w-6
                    -translate-y-1/2 cursor-pointer items-center justify-center rounded-lg transition-colors"
            >
                <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
            </button>
        </div>

        <!-- Breadcrumb & Actions -->
        <div class="mb-3 flex items-center justify-between">
            <div class="flex items-center gap-1 text-sm">
                <span
                    v-for="(part, index) in breadcrumb"
                    :key="index"
                    class="text-stone-gray/60 flex items-center gap-1"
                >
                    <span v-if="index > 0" class="text-stone-gray/40">/</span>
                    <span
                        class="hover:text-soft-silk cursor-pointer transition-colors"
                        @click="navigateToPath(breadcrumb.slice(1, index + 1))"
                    >
                        {{ part }}
                    </span>
                </span>
            </div>
            <div class="flex items-center gap-2">
                <button
                    @click="expandAll"
                    title="Expand All"
                    class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 rounded-md p-1 transition-colors"
                >
                    <UiIcon name="MdiExpandAllOutline" class="h-4 w-4" />
                </button>
                <button
                    @click="collapseAll"
                    title="Collapse All"
                    class="text-stone-gray/60 hover:text-soft-silk hover:bg-soft-silk/5 rounded-md p-1 transition-colors"
                >
                    <UiIcon name="MdiCollapseAllOutline" class="h-4 w-4" />
                </button>
            </div>
        </div>

        <!-- File Tree -->
        <div
            class="bg-obsidian/50 border-stone-gray/20 flex-grow overflow-y-auto dark-scrollbar rounded-lg border"
        >
            <UiGraphNodeUtilsGithubFileTreeNode
                v-if="filteredTree"
                :node="filteredTree"
                :level="0"
                :expanded-paths="expandedPaths"
                :selected-paths="Array.from(selectedPaths).map((node) => node.path)"
                @toggle-expand="toggleExpand"
                @toggle-select="toggleSelect"
                @toggle-select-preview="(node) => (selectPreview = node)"
                @navigate-to="navigateToPath"
            ></UiGraphNodeUtilsGithubFileTreeNode>
        </div>

        <!-- Actions -->
        <div class="mt-4 flex justify-end gap-3">
            <button
                @click="$emit('close')"
                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk rounded-lg px-4 py-2 transition-colors"
            >
                Cancel
            </button>
            <button
                @click="confirmSelection"
                class="bg-ember-glow hover:bg-terracotta-clay text-soft-silk rounded-lg px-4 py-2 transition-colors"
                :disabled="selectedPaths.size === 0"
                :class="{ 'cursor-not-allowed opacity-50': selectedPaths.size === 0 }"
            >
                Confirm Selection ({{ selectedPaths.size }})
            </button>
        </div>
    </div>

    <div
        class="bg-obsidian/50 border-stone-gray/20 mx-4 flex h-full grow overflow-hidden rounded-lg border p-4"
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
            <div
                v-html="previewHtml"
                class="file-preview dark-scrollbar grow overflow-y-auto"
            ></div>
        </div>
    </div>
</template>
