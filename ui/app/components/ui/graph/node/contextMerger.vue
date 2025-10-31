<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataContextMerger } from '@/types/graph';
import { ContextMergerModeEnum } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode', 'update:unlinkNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const blockDefinition = getBlockById('primary-context-merger');

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataContextMerger>>();

// --- Methods ---
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
        class="bg-golden-ochre border-golden-ochre-dark relative flex h-full w-full flex-col
            rounded-3xl border-2 p-4 pt-3 shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-golden-ochre-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-center">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                />
                <span class="dark:text-soft-silk/80 text-anthracite text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
        </div>

        <!-- Block Content -->
        <div class="flex flex-1 items-center justify-center gap-4">
            <!-- Choose between multiple input modes : full, summary, last_n -->
            <template
                v-for="mode in [
                    ContextMergerModeEnum.FULL,
                    ContextMergerModeEnum.SUMMARY,
                    ContextMergerModeEnum.LAST_N,
                ]"
                :key="mode"
            >
                <div
                    class="flex w-fit items-center justify-between rounded-lg border bg-white/10
                        px-2 py-1 hover:bg-white/20"
                    :class="{
                        'border-golden-ochre-dark bg-white/20': props.data.mode === mode,
                        'hover:border-golden-ochre-dark/50 border-transparent':
                            props.data.mode !== mode,
                    }"
                    @click="props.data.mode = mode"
                >
                    <label class="dark:text-soft-silk text-anthracite font-medium capitalize">
                        {{ mode.replace('_', ' ') }}
                    </label>
                </div>
            </template>
        </div>
    </div>

    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        type="target"
        :node-id="props.id"
        :options="[]"
        :style="{ left: '50%' }"
        :is-dragging="props.dragging"
        class="handletopcustom"
        multiple-input
    />
    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        :node-id="props.id"
        :options="[]"
        type="source"
        :is-dragging="props.dragging"
    />
</template>

<style>
.handletopcustom > .vue-flow__handle {
    width: 150px !important;
}
</style>
