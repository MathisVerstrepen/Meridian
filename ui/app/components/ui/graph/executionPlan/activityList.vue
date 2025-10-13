<script lang="ts" setup>
import type { ExecutionPlanResponse } from '@/types/chat';
import { NodeTypeEnum } from '@/types/enums';
import { useVueFlow } from '@vue-flow/core';

const props = defineProps<{
    plan: ExecutionPlanResponse | null;
    doneTable: Record<string, number>;
    selectedCategories: Record<string, boolean>;
    graphId: string;
}>();

// --- Composables ---
const { fitView } = useVueFlow('main-graph-' + props.graphId);

// --- Methods ---
const focusToNode = (nodeId: string) => {
    fitView({
        nodes: [nodeId],
        duration: 1000,
        padding: 2,
    });
};
</script>

<template>
    <ul
        class="hide-scrollbar mb-2 flex h-min w-full flex-wrap items-center justify-center gap-2 overflow-y-auto"
    >
        <li
            v-for="step in plan?.steps"
            v-show="
                (selectedCategories.not_started && doneTable[step.node_id] === 0) ||
                (selectedCategories.in_progress && doneTable[step.node_id] === 1) ||
                (selectedCategories.done && doneTable[step.node_id] === 2)
            "
            :key="step.node_id"
            class="bg-stone-gray/10 border-stone-gray/20 text-soft-silk relative flex h-10 w-[48%] items-center
                justify-between overflow-hidden rounded-lg border-2 px-2 py-2 transition-all duration-200
                ease-in-out"
            :class="{
                '!bg-olive-grove/20 !border-olive-grove/50': doneTable[step.node_id] === 2,
                '!bg-slate-blue/20 !border-slate-blue/50': doneTable[step.node_id] === 1,
            }"
        >
            <span
                class="hover:text-obsidian absolute top-0 left-0 h-2 w-8 rounded-tl-lg rounded-br-xl"
                :class="{
                    'bg-terracotta-clay': step.node_type === NodeTypeEnum.PARALLELIZATION,
                    'bg-olive-grove': step.node_type === NodeTypeEnum.TEXT_TO_TEXT,
                    'bg-sunbaked-sand-dark': step.node_type === NodeTypeEnum.ROUTING,
                }"
            />
            <span class="mx-2 text-[9px] font-bold">{{ step.node_id.slice(0, 24) }}...</span>
            <button
                class="nodrag bg-stone-gray/10 hover:bg-stone-gray/20 dark:text-soft-silk text-anthracite relative flex h-6
                    w-6 flex-shrink-0 cursor-pointer items-center justify-center rounded-2xl transition-all duration-200
                    ease-in-out"
                @click="focusToNode(step.node_id)"
            >
                <UiIcon name="LetsIconsTarget" class="h-4 w-4" />
            </button>
        </li>
    </ul>
</template>

<style scoped></style>
