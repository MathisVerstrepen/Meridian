<script lang="ts" setup>
import { motion } from 'motion-v';

defineProps<{
    graphId: string;
    nodeId: string;
    selected: boolean;
    source: 'generator' | 'input';
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
    <AnimatePresence>
        <motion.div
            v-if="selected"
            key="run-toolbar"
            :initial="{ opacity: 0, scale: 0, translateY: 25 }"
            :animate="{ opacity: 1, scale: 1, translateY: 0 }"
            :exit="{ opacity: 0, scale: 0, translateY: 25 }"
            class="bg-soft-silk/10 border-soft-silk/20 absolute -top-16 left-1/2 z-10 flex -translate-x-1/2
                items-center justify-between rounded-2xl border-2 p-1 shadow-lg backdrop-blur-md"
        >
            <button
                class="hover:bg-soft-silk/20 flex cursor-pointer items-center justify-center rounded-xl p-2
                    transition-colors duration-200 ease-in-out"
                title="Run all nodes above"
                @click="setExecutionPlan(graphId, nodeId, 'upstream')"
                v-if="source === 'generator'"
            >
                <UiIcon name="CodiconRunAbove" class="text-soft-silk h-5 w-5"> </UiIcon>
            </button>

            <button
                class="hover:bg-soft-silk/20 flex cursor-pointer items-center justify-center rounded-xl p-2
                    transition-colors duration-200 ease-in-out"
                title="Run this node"
                @click="setExecutionPlan(graphId, nodeId, 'self')"
                v-if="source === 'generator'"
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
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
