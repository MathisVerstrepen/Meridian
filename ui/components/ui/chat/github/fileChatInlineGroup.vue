<script lang="ts" setup>
import type { FileTreeNode } from '@/types/github';

const MAX_ITEMS_COLLAPSE = 5;

const props = defineProps<{
    extractedGithubFiles: FileTreeNode[];
}>();

// --- Local State ---
const repoMap = ref<Record<string, FileTreeNode[]>>({});
const isCollapsed = ref(true);

// --- Watchers ---
watch(
    () => props.extractedGithubFiles,
    (newFiles) => {
        repoMap.value = {};
        isCollapsed.value = true;

        newFiles.forEach((file) => {
            const splitPath = file.path.split('/');
            const repo = splitPath[0] + '/' + splitPath[1];
            const filePath = splitPath.slice(2).join('/');
            file.path = filePath;

            repoMap.value[repo] = repoMap.value[repo] || [];
            repoMap.value[repo].push(file);
        });
    },
    { immediate: true },
);
</script>

<template>
    <div v-for="(files, repo) in repoMap" :key="repo" class="relative mt-4 mb-2">
        <a
            class="dark:bg-anthracite bg-anthracite/50 border-stone-gray/10 text-soft-silk/50 absolute -top-2.5 left-2
                flex items-center rounded-md border px-2 py-0.5 text-xs font-medium no-underline"
            :href="`https://github.com/${repo}`"
            target="_blank"
            rel="noopener noreferrer"
        >
            <UiIcon name="MdiGithub" class="mr-1 inline-block h-4 w-4" />
            {{ repo }}
        </a>
        <div class="border-stone-gray/10 flex flex-wrap gap-1 rounded-lg border p-2 pt-4">
            <UiChatGithubFileChatInlineChip
                v-for="file in files.slice(0, isCollapsed ? MAX_ITEMS_COLLAPSE : files.length)"
                :key="file.path"
                :file="file"
            ></UiChatGithubFileChatInlineChip>
            <div
                class="text-stone-gray/80 hover:bg-obsidian/20 flex cursor-pointer items-center rounded-lg px-2 py-1
                    text-xs font-bold transition-colors duration-200 ease-in-out"
                v-if="isCollapsed && files.length > MAX_ITEMS_COLLAPSE"
                @click="isCollapsed = false"
                title="Show more files"
            >
                <span>{{ files.length - MAX_ITEMS_COLLAPSE }} more...</span>
            </div>
            <div
                class="text-stone-gray/80 hover:bg-obsidian/20 flex cursor-pointer items-center rounded-lg px-2 py-1
                    text-xs font-bold transition-colors duration-200 ease-in-out"
                v-if="!isCollapsed"
                @click="isCollapsed = true"
                title="Show less files"
            >
                <span>Show less...</span>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
