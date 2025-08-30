<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataGithub } from '@/types/graph';

const emit = defineEmits(['updateNodeInternals', 'update:canvasName', 'update:deleteNode']);

// --- Props ---
const props = defineProps<NodeProps<DataGithub>>();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Stores ---
const githubStore = useGithubStore();

// --- State from Stores ---
const { isGithubConnected } = storeToRefs(githubStore);

// --- Composables ---
const { getBlockById } = useBlocks();

// --- Constants ---
const blockDefinition = getBlockById('primary-github-context');
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="blockDefinition?.minSize?.height"
        color="transparent"
        :nodeId="props.id"
    ></NodeResizer>

    <UiGraphNodeUtilsRunToolbar
        :graphId="graphId"
        :nodeId="props.id"
        :selected="props.selected"
        source="input"
        @update:deleteNode="emit('update:deleteNode', props.id)"
    ></UiGraphNodeUtilsRunToolbar>

    <div
        class="bg-github border-soft-silk/10 relative flex h-full w-full flex-col rounded-3xl border-2 p-4 pt-3
            text-black shadow-lg transition-all duration-200 ease-in-out"
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
        </div>

        <div class="flex h-full flex-col items-center justify-start gap-4">
            <UiGraphNodeUtilsGithubRepoSelect
                v-if="isGithubConnected"
                class="shrink-0"
                :repo="props.data.repo"
                :setRepo="
                    (repo) => {
                        props.data.repo = repo;
                        emit('updateNodeInternals');
                    }
                "
            ></UiGraphNodeUtilsGithubRepoSelect>

            <UiGraphNodeUtilsGithubFileListVue
                v-if="props.data.repo"
                class="shrink-0"
                :files="props.data.files"
                :setFiles="
                    (files) => {
                        props.data.files = files;
                        emit('updateNodeInternals');
                    }
                "
                :repo="props.data.repo"
                :nodeId="props.id"
            />

            <div
                v-else
                class="text-soft-silk/20 flex w-full grow items-center justify-center text-xs font-bold"
            >
                <p v-if="isGithubConnected">Select a repository</p>
                <p v-else class="text-center">
                    Connect to GitHub to select a repository<br />
                    in Settings > Blocks > GitHub
                </p>
            </div>
        </div>
    </div>

    <UiGraphNodeUtilsHandleAttachment type="source" :id="props.id" :isDragging="props.dragging" />
</template>
