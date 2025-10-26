<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataGithub } from '@/types/graph';
import type { RepositoryInfo } from '@/types/github';

const emit = defineEmits([
    'updateNodeInternals',
    'update:canvasName',
    'update:deleteNode',
    'update:unlinkNode',
]);

// --- Props ---
const props = defineProps<NodeProps<DataGithub>>();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Stores ---
const githubStore = useGithubStore();
const gitlabStore = useGitlabStore();
const repositoryStore = useRepositoryStore();

// --- State from Stores ---
const { isGithubConnected } = storeToRefs(githubStore);
const { isGitlabConnected } = storeToRefs(gitlabStore);
const isAnyGitProviderConnected = computed(
    () => isGithubConnected.value || isGitlabConnected.value,
);

// --- Composables ---
const { getBlockById } = useBlocks();

// --- Actions ---
const { fetchRepositories } = repositoryStore;

// --- Constants ---
const blockDefinition = getBlockById('primary-github-context');

watch(
    () => props.data.repo,
    (newRepo) => {
        if (newRepo) {
            props.data.files = [];
            props.data.branch = undefined;
            emit('updateNodeInternals');
        }
    },
);

onMounted(() => {
    fetchRepositories();
});
</script>

<template>
    <NodeResizer
        :is-visible="true"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
        :graph-id="graphId"
        :node-id="props.id"
        :selected="props.selected"
        source="input"
        :in-group="props.parentNodeId !== undefined"
        @update:delete-node="emit('update:deleteNode', props.id)"
        @update:unlink-node="emit('update:unlinkNode', props.id)"
    />

    <div
        class="bg-github border-soft-silk/10 relative flex h-full w-full flex-col rounded-3xl
            border-2 p-4 pt-3 text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-github !shadow-[0px_0px_15px_3px]': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex grow items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                />
                <span class="dark:text-soft-silk/80 text-anthracite text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
            <span v-if="props.data.repo" class="text-stone-gray/60 flex items-center text-sm">
                {{ props.data.branch || props.data.repo.default_branch
                }}<UiIcon name="MdiSourceBranch" class="ml-1 h-4 w-4" />
            </span>
        </div>

        <div class="flex h-full flex-col items-center justify-start gap-4">
            <UiGraphNodeUtilsGithubRepoSelect
                v-if="isAnyGitProviderConnected"
                v-model:current-repo="props.data.repo as unknown as RepositoryInfo"
                class="shrink-0"
            />

            <UiGraphNodeUtilsGithubFileList
                v-if="props.data.repo"
                :key="props.data.repo.full_name"
                class="shrink-0"
                :files="props.data.files"
                :branch="props.data.branch"
                :set-files="
                    (files) => {
                        props.data.files = files;
                        emit('updateNodeInternals');
                    }
                "
                :set-branch="
                    (branch) => {
                        props.data.branch = branch;
                        emit('updateNodeInternals');
                    }
                "
                :repo="props.data.repo as unknown as RepositoryInfo"
                :node-id="props.id"
            />

            <div
                v-else
                class="text-soft-silk/20 flex w-full grow items-center justify-center text-xs
                    font-bold"
            >
                <p v-if="isAnyGitProviderConnected">Select a repository</p>
                <p v-else class="text-center">
                    Connect to GitHub or GitLab to select a repository<br />
                    in Settings > Blocks
                </p>
            </div>
        </div>
    </div>

    <UiGraphNodeUtilsHandleAttachment :id="props.id" type="source" :is-dragging="props.dragging" />
</template>
