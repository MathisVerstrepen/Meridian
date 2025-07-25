<script lang="ts" setup>
import { motion } from 'motion-v';

const emit = defineEmits(['update:deleteNode']);

defineProps<{
    graphId: string;
    nodeId: string;
    selected: boolean;
    source: 'generator' | 'input';
}>();

// --- Composables ---
const { setExecutionPlan } = useExecutionPlan();
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

            <hr class="bg-soft-silk/20 mx-2 h-6 w-[3px] self-center rounded-full" />

            <button
                @click.stop="emit('update:deleteNode')"
                class="hover:bg-terracotta-clay/25 text-terracotta-clay flex cursor-pointer items-center justify-center
                    rounded-xl p-2 transition-colors duration-200 ease-in-out"
            >
                <UiIcon name="MaterialSymbolsDeleteRounded" class="text-terracotta-clay h-5 w-5" />
            </button>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
