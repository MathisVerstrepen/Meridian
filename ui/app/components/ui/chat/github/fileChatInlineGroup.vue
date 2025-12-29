<script lang="ts" setup>
import type { FileTreeNode, ExtractedIssue } from '@/types/github';

const MAX_ITEMS_COLLAPSE = 5;

const props = defineProps<{
    extractedGithubFiles: FileTreeNode[];
    extractedGithubIssues?: ExtractedIssue[];
}>();

interface RepoGroup {
    files: FileTreeNode[];
    issues: ExtractedIssue[];
}

// --- Local State ---
const repoMap = ref<Record<string, RepoGroup>>({});
const isCollapsed = ref(true);

// --- Helper ---
const getRepoKeyFromUrl = (url: string): string => {
    try {
        const urlObj = new URL(url);
        const pathParts = urlObj.pathname.split('/').filter(Boolean);
        if (pathParts.length >= 2) {
            const provider = urlObj.hostname.includes('gitlab') ? 'gitlab' : 'github';
            return `${provider}:${pathParts[0]}/${pathParts[1]}`;
        }
    } catch {
        console.error('Invalid URL:', url);
    }
    return 'unknown:unknown/repository';
};

// --- Watchers ---
watch(
    [() => props.extractedGithubFiles, () => props.extractedGithubIssues],
    ([newFiles, newIssues]) => {
        repoMap.value = {};
        isCollapsed.value = true;

        // Process Files
        newFiles.forEach((file) => {
            const splitPath = file.path.split('/');
            const repo = splitPath[0] + ':' + splitPath[1] + '/' + splitPath[2];
            const filePath = splitPath.slice(3).join('/');

            // Clone to avoid mutating prop directly if reused
            const fileItem = { ...file, path: filePath };

            if (!repoMap.value[repo]) {
                repoMap.value[repo] = { files: [], issues: [] };
            }
            repoMap.value[repo].files.push(fileItem);
        });

        // Process Issues
        if (newIssues) {
            newIssues.forEach((issue) => {
                const repo = getRepoKeyFromUrl(issue.url);
                if (!repoMap.value[repo]) {
                    repoMap.value[repo] = { files: [], issues: [] };
                }
                repoMap.value[repo].issues.push(issue);
            });
        }
    },
    { immediate: true },
);
</script>

<template>
    <div v-for="(group, repo) in repoMap" :key="repo" class="relative mt-4 mb-2">
        <a
            class="dark:bg-anthracite bg-anthracite/50 border-stone-gray/10 text-soft-silk/50
                absolute -top-2.5 left-2 flex items-center rounded-md border px-2 py-0.5 text-xs
                font-medium no-underline"
            :title="repo.split(':')[1]"
            :href="
                repo.startsWith('gitlab')
                    ? `https://gitlab.com/${repo.split(':')[1]}`
                    : `https://github.com/${repo.split(':')[1]}`
            "
            target="_blank"
            rel="noopener noreferrer"
        >
            <UiIcon
                :name="repo.startsWith('gitlab') ? 'MdiGitlab' : 'MdiGithub'"
                class="mr-1 inline-block h-4 w-4"
            />
            {{ repo.split(':')[1] }}
        </a>
        <div class="border-stone-gray/10 flex flex-wrap gap-1 rounded-lg border p-2 pt-4">
            <!-- Files -->
            <UiChatGithubFileChatInlineChip
                v-for="file in group.files.slice(
                    0,
                    isCollapsed ? MAX_ITEMS_COLLAPSE : group.files.length,
                )"
                :key="file.path"
                :file="file"
            />

            <!-- Issues/PRs -->
            <UiChatGithubIssueChatInlineChip
                v-for="issue in group.issues.slice(
                    0,
                    isCollapsed
                        ? Math.max(0, MAX_ITEMS_COLLAPSE - group.files.length)
                        : group.issues.length,
                )"
                :key="issue.url"
                :issue="issue"
            />

            <!-- Expand/Collapse Controls -->
            <div
                v-if="isCollapsed && group.files.length + group.issues.length > MAX_ITEMS_COLLAPSE"
                class="text-stone-gray/80 hover:bg-obsidian/20 flex cursor-pointer items-center
                    rounded-lg px-2 py-1 text-xs font-bold transition-colors duration-200
                    ease-in-out"
                title="Show more"
                @click="isCollapsed = false"
            >
                <span
                    >{{
                        group.files.length + group.issues.length - MAX_ITEMS_COLLAPSE
                    }}
                    more...</span
                >
            </div>
            <div
                v-if="!isCollapsed"
                class="text-stone-gray/80 hover:bg-obsidian/20 flex cursor-pointer items-center
                    rounded-lg px-2 py-1 text-xs font-bold transition-colors duration-200
                    ease-in-out"
                title="Show less"
                @click="isCollapsed = true"
            >
                <span>Show less...</span>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
