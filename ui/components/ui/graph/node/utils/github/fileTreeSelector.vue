<script lang="ts" setup>
import type { FileTreeNode } from '@/types/github';

// --- Props ---
const props = defineProps<{
    treeData: FileTreeNode;
    initialSelectedPaths?: FileTreeNode[];
}>();

// --- Emits ---
const emit = defineEmits(['update:selectedFiles', 'close']);

// --- State ---
const searchQuery = ref('');
const expandedPaths = ref<Set<string>>(new Set(['.'])); // Start with root expanded
const selectedPaths = ref<Set<FileTreeNode>>(new Set(props.initialSelectedPaths || []));
const breadcrumb = ref<string[]>(['root']);

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

// --- Methods ---
const toggleExpand = (path: string) => {
    if (expandedPaths.value.has(path)) {
        expandedPaths.value.delete(path);
    } else {
        expandedPaths.value.add(path);
    }
};

const toggleSelect = (node: FileTreeNode) => {
    const existingNode = [...selectedPaths.value].find((item) => item.path === node.path);

    if (existingNode) {
        selectedPaths.value.delete(existingNode);
    } else {
        const nodeCopy = { ...node };
        delete nodeCopy.children;
        selectedPaths.value.add(nodeCopy);
    }

    emit('update:selectedFiles', Array.from(selectedPaths.value));
};

const navigateToPath = (pathParts: string[]) => {
    breadcrumb.value = ['root', ...pathParts];
};

const confirmSelection = () => {
    emit('close', Array.from(selectedPaths.value));
};
</script>

<template>
    <div class="flex h-full w-1/2 flex-col">
        <!-- Header -->
        <div class="border-stone-gray/20 mb-4 flex items-center justify-between border-b pb-4">
            <h2 class="text-soft-silk text-xl font-bold">Select Files</h2>
            <button
                @click="$emit('close')"
                class="text-stone-gray hover:text-soft-silk transition-colors"
            >
                <UiIcon name="MaterialSymbolsClose" class="h-6 w-6" />
            </button>
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

        <!-- Breadcrumb -->
        <div class="mb-3 flex items-center gap-1 text-sm">
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

        <!-- File Tree -->
        <div
            class="bg-obsidian/50 border-stone-gray/20 flex-grow overflow-y-auto rounded-lg border"
        >
            <UiGraphNodeUtilsGithubFileTreeNode
                v-if="filteredTree"
                :node="filteredTree"
                :level="0"
                :expanded-paths="expandedPaths"
                :selected-paths="Array.from(selectedPaths).map((node) => node.path)"
                @toggle-expand="toggleExpand"
                @toggle-select="toggleSelect"
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
</template>
