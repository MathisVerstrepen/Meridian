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
const emit = defineEmits(['toggleExpand', 'toggleSelect', 'navigateTo']);

const { getIconForFile } = useFileIcons();

// --- Computed ---
const isExpanded = computed(() => props.expandedPaths.has(props.node.path));
const isSelected = computed(() => props.selectedPaths.includes(props.node.path));
const hasChildren = computed(() => props.node.children && props.node.children.length > 0);
const indent = computed(() => props.level * 20);
const fileIcon = computed(() => {
    if (props.node.type === 'directory') {
        return isExpanded.value ? 'MdiFolderOpenOutline' : 'MdiFolderOutline';
    } else if (props.node.type === 'file') {
        const fileIcon = getIconForFile(props.node.name);
        if (fileIcon) return 'fileTree/' + fileIcon;
    }
    return 'MdiFileOutline';
});
</script>

<template>
    <div>
        <!-- Current Node -->
        <div
            class="group hover:bg-stone-gray/10 flex items-center py-1 pr-2 pl-4 transition-colors"
            :style="{ paddingLeft: `${indent + 4}px` }"
            @click="$emit('toggleExpand', node.path)"
        >
            <!-- Expand/Collapse Button -->
            <button
                v-if="hasChildren"
                class="text-stone-gray/60 hover:text-soft-silk mr-1 flex h-5 w-5 items-center justify-center
                    transition-colors"
            >
                <UiIcon
                    :name="'FlowbiteChevronDownOutline'"
                    class="h-4 w-4 transition-transform duration-200 ease-in-out"
                    :class="{ '-rotate-90': !isExpanded }"
                />
            </button>
            <div v-else class="w-5"></div>

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
            <input
                :id="`checkbox-${node.path}`"
                type="checkbox"
                :checked="isSelected"
                @change="$emit('toggleSelect', node)"
                @click.stop
                class="bg-obsidian border-stone-gray/40 text-ember-glow focus:ring-ember-glow mr-2 h-4 w-4 rounded"
            />

            <!-- Name -->
            <label
                :for="`checkbox-${node.path}`"
                class="text-soft-silk/90 hover:text-soft-silk cursor-pointer transition-colors select-none"
                :class="{ 'font-medium': isSelected }"
                @click.stop
            >
                {{ node.name }}
            </label>

            <!-- Path info (for debugging, can be removed) -->
            <span class="text-stone-gray/40 ml-2 text-xs select-none">
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
                @navigate-to="$emit('navigateTo', $event)"
            ></UiGraphNodeUtilsGithubFileTreeNode>
        </div>
    </div>
</template>
