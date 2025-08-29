<script lang="ts" setup>
import { type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import { NodeTypeEnum } from '@/types/enums';
import type { DataPrompt } from '@/types/graph';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const { saveGraph } = useCanvasSaveStore();
const { searchNode } = useAPI();
const nodeRegistry = useNodeRegistry();
const blockDefinition = getBlockById('primary-prompt-text');

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataPrompt>>();

// --- Methods ---
const doneAction = async (generateNext: boolean) => {
    await saveGraph();
    if (!generateNext) {
        emit('updateNodeInternals');
        return;
    }
    const nodes = await searchNode(graphId.value, props.id, 'downstream', [
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
        NodeTypeEnum.TEXT_TO_TEXT,
    ]);
    let jobs = [];
    for (const node of nodes) {
        jobs.push(nodeRegistry.execute(node));
    }
    await Promise.all(jobs);
};
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
        class="bg-slate-blue border-slate-blue-dark relative flex h-full w-full flex-col rounded-3xl border-2 p-4
            pt-3 shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-slate-blue-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                />
                <span
                    class="dark:text-soft-silk/80 text-anthracite -translate-y-0.5 text-lg font-bold"
                >
                    {{ blockDefinition?.name }}
                </span>
            </label>
        </div>

        <!-- Textarea for Prompt -->
        <UiGraphNodeUtilsTextarea
            :reply="props.data.prompt"
            :readonly="false"
            color="slate-blue"
            placeholder="Enter your prompt here"
            :autoscroll="false"
            @update:reply="
                (value: string) => {
                    props.data.prompt = value;
                }
            "
            @update:doneAction="doneAction"
            :parseError="false"
        ></UiGraphNodeUtilsTextarea>
    </div>

    <UiGraphNodeUtilsHandlePrompt type="target" :id="props.id" :isDragging="props.dragging" />
    <UiGraphNodeUtilsHandlePrompt type="source" :id="props.id" :isDragging="props.dragging" />
</template>

<style scoped></style>
