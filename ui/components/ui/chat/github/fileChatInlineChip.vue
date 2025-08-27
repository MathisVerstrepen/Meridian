<script lang="ts" setup>
import type { FileTreeNode } from '@/types/github';

const props = defineProps<{
    file: FileTreeNode;
}>();

const { getIconForFile } = useFileIcons();

const fileIcon = computed(() => {
    const fileIcon = getIconForFile(props.file.name);
    if (fileIcon) return 'fileTree/' + fileIcon;
    return 'MdiFileOutline';
});
</script>

<template>
    <div
        class="border-stone-gray/25 text-stone-gray/80 bg-obsidian/50 flex items-center rounded-lg border px-2 py-1
            text-xs font-bold"
    >
        <UiIcon
            :name="fileIcon"
            class="mr-2 h-4 w-4 text-transparent"
            :class="{
                '!text-stone-gray/70': fileIcon === 'MdiFileOutline',
            }"
        />
        <span>{{ props.file.path }}</span>
    </div>
</template>

<style scoped></style>
