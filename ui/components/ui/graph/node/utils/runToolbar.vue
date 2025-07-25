<script lang="ts" setup>
import { Position } from '@vue-flow/core';
import { NodeToolbar } from '@vue-flow/node-toolbar';

defineProps<{
    graphId: string;
    nodeId: string;
}>();

// --- Composables ---
const { getExecutionPlan } = useAPI();
const { error } = useToast();
const graphEvents = useGraphEvents();

// --- Core Logic Functions ---
const setExecutionPlan = async (
    graphId: string,
    nodeId: string,
    direction: 'upstream' | 'self' | 'downstream',
) => {
    try {
        const planRes = await getExecutionPlan(graphId, nodeId, direction);
        if (!planRes) {
            error('Failed to get execution plan', { title: 'API Error' });
            return;
        }

        graphEvents.emit('execution-plan', {
            graphId,
            nodeId,
            direction,
            plan: planRes,
        });
    } catch (err) {
        error('Failed to get execution plan', { title: 'API Error' });
    }
};
</script>

<template>
    <NodeToolbar
        :position="Position.Top"
        class="bg-soft-silk/10 border-soft-silk/20 flex items-center justify-between rounded-2xl border-2 p-1
            shadow-lg backdrop-blur-md"
    >
        <button
            class="hover:bg-soft-silk/20 flex cursor-pointer items-center justify-center rounded-xl p-2
                transition-colors duration-200 ease-in-out"
            title="Run all nodes above"
            @click="setExecutionPlan(graphId, nodeId, 'upstream')"
        >
            <UiIcon name="CodiconRunAbove" class="text-soft-silk h-5 w-5"> </UiIcon>
        </button>
        <button
            class="hover:bg-soft-silk/20 flex cursor-pointer items-center justify-center rounded-xl p-2
                transition-colors duration-200 ease-in-out"
            title="Run this node"
            @click="setExecutionPlan(graphId, nodeId, 'self')"
        >
            <UiIcon name="CodiconRunAll" class="text-soft-silk h-5 w-5"> </UiIcon>
        </button>
        <button
            class="hover:bg-soft-silk/20 flex cursor-pointer items-center justify-center rounded-xl p-2
                transition-colors duration-200 ease-in-out"
            title="Run all nodes below"
            @click="setExecutionPlan(graphId, nodeId, 'downstream')"
        >
            <UiIcon name="CodiconRunBelow" class="text-soft-silk h-5 w-5"> </UiIcon>
        </button>
    </NodeToolbar>
</template>

<style scoped></style>
