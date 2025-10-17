<script lang="ts" setup>
import type { Node } from '@vue-flow/core';
import { NodeTypeEnum } from '@/types/enums';

const props = defineProps<{
    node: Node;
    graphId: string;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();

// --- Composables ---
const { saveGraph } = useCanvasSaveStore();
const { searchNode } = useAPI();
const nodeRegistry = useNodeRegistry();

// --- Methods ---
const doneAction = async (generateNext: boolean) => {
    await saveGraph();
    if (!generateNext) {
        return;
    }
    const nodes = await searchNode(props.graphId, props.node.id, 'downstream', [
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
        NodeTypeEnum.TEXT_TO_TEXT,
    ]);
    const jobs = [];
    for (const node of nodes) {
        jobs.push(nodeRegistry.execute(node));
    }
    await Promise.all(jobs);
};
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Original Prompt
        </h3>
        <UiGraphNodeUtilsTextarea
            class="grow"
            :reply="node.data.prompt"
            :readonly="false"
            color="grey"
            placeholder="Enter your prompt here"
            :autoscroll="false"
            :parse-error="false"
            @update:reply="(value: string) => setNodeDataKey('prompt', value)"
            @update:done-action="doneAction"
        />
    </div>
</template>

<style scoped></style>
