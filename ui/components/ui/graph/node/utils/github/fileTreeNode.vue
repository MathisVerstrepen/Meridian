<script lang="ts" setup>
import type { FileTreeNode } from '@/types/github';

// --- Props ---
const props = defineProps<{
    node: FileTreeNode;
    level: number;
    expandedPaths: Set<string>;
    selectedPaths: Array<string>;
}>();

// --- Emits ---
defineEmits(['toggleExpand', 'toggleSelect', 'toggleSelectPreview', 'navigateTo']);

const { getIconForFile } = useFileIcons();

// --- Helper Functions ---
const getAllDescendantFiles = (node: FileTreeNode): FileTreeNode[] => {
    if (node.type === 'file') {
        return [node];
    }
    if (!node.children || node.children.length === 0) {
        return [];
    }
    // Recursively flatten the children to get all descendant files
    return node.children.flatMap(getAllDescendantFiles);
};

// --- Computed ---
const hasChildren = computed(() => props.node.children && props.node.children.length > 0);
const isExpanded = computed(() => props.expandedPaths.has(props.node.path));
const indent = computed(() => props.level * 20);

const directorySelectionState = computed(() => {
    if (props.node.type !== 'directory') {
        return null;
    }
    const descendantFiles = getAllDescendantFiles(props.node);
    if (descendantFiles.length === 0) {
        return 'none';
    }
    const selectedCount = descendantFiles.filter((file) =>
        props.selectedPaths.includes(file.path),
    ).length;

    if (selectedCount === 0) return 'none';
    if (selectedCount === descendantFiles.length) return 'all';
    return 'some';
});

const isSelected = computed(() => {
    if (props.node.type === 'file') {
        return props.selectedPaths.includes(props.node.path);
    }
    return directorySelectionState.value === 'all';
});

const isIndeterminate = computed(() => {
    if (props.node.type === 'file') {
        return false;
    }
    return directorySelectionState.value === 'some';
});

const fileIcon = computed(() => {
    if (props.node.type === 'directory') {
        return isExpanded.value ? 'MdiFolderOpenOutline' : 'MdiFolderOutline';
    } else if (props.node.type === 'file') {
        const icon = getIconForFile(props.node.name);
        if (icon) return 'fileTree/' + icon;
    }
    return 'MdiFileOutline';
});
</script>

<template>
    <div>
        <!-- Current Node -->
        <div
            class="group hover:bg-stone-gray/10 flex cursor-pointer items-center py-1 pr-2 pl-4 transition-colors"
            :style="{ paddingLeft: `${indent + 4}px` }"
            @click="
                () => {
                    if (props.node.type === 'file') {
                        $emit('toggleSelectPreview', node);
                    } else {
                        $emit('toggleExpand', node.path);
                    }
                }
            "
        >
            <!-- Expand/Collapse Button -->
            <button
                v-if="hasChildren"
                class="text-stone-gray/60 hover:text-soft-silk mr-1 flex h-5 w-5 items-center justify-center
                    transition-colors"
                @click.stop="$emit('toggleExpand', node.path)"
            >
                <UiIcon
                    :name="'FlowbiteChevronDownOutline'"
                    class="h-4 w-4 transition-transform duration-200 ease-in-out"
                    :class="{ '-rotate-90': !isExpanded }"
                />
            </button>
            <div v-else class="mr-1 w-5"/>

            <!-- Icon -->
            <UiIcon
                :name="fileIcon"
                class="mr-2 h-4 w-4 text-transparent"
                :class="{
                    '!text-stone-gray/70':
                        node.type === 'directory' || fileIcon === 'MdiFileOutline',
                }"
            />

            <!-- Checkbox -->
            <UiGraphNodeUtilsGithubCheckbox
                v-model="isSelected"
                :label="node.name"
                :indeterminate="isIndeterminate"
                @click.stop
                @set-state="() => $emit('toggleSelect', node)"
            />

            <!-- Path info -->
            <span class="text-stone-gray/40 ml-auto pl-4 text-xs select-none">
                {{ node.path }}
            </span>
        </div>

        <!-- Children -->
        <div v-if="isExpanded && hasChildren">
            <UiGraphNodeUtilsGithubFileTreeNode
                v-for="child in node.children"
                :key="child.path"
                :node="child"
                :level="level + 1"
                :expanded-paths="expandedPaths"
                :selected-paths="selectedPaths"
                @toggle-expand="$emit('toggleExpand', $event)"
                @toggle-select="$emit('toggleSelect', $event)"
                @toggle-select-preview="$emit('toggleSelectPreview', $event)"
                @navigate-to="$emit('navigateTo', $event)"
            />
        </div>
    </div>
</template>
