<script lang="ts" setup>
import { useVueFlow } from '@vue-flow/core';
import { Controls, ControlButton } from '@vue-flow/controls';
import { DEFAULT_NODE_ID } from '@/constants';
import { ExecutionPlanDirectionEnum } from '@/types/enums';

const props = defineProps<{
    graphId: string;
}>();

// --- Stores ---
const sidebarSelectorStore = useSidebarCanvasStore();

// --- State from Stores (Reactive Refs) ---
const { isLeftOpen } = storeToRefs(sidebarSelectorStore);

// --- Composables ---
const { getNodes, removeNodes } = useVueFlow('main-graph-' + props.graphId);
const { setExecutionPlan } = useExecutionPlan();

// --- Core Logic Functions ---
const deleteAllNodes = () => {
    if (getNodes.value.length === 0) return;

    if (
        window.confirm('Are you sure you want to delete all nodes? This action cannot be undone.')
    ) {
        removeNodes(getNodes.value);
    }
};
</script>

<template>
    <Controls
        position="top-left"
        class="!top-2 !z-10 !m-0 transition-all duration-200 ease-in-out"
        :class="{
            '!left-[4rem]': !isLeftOpen,
        }"
    >
        <div class="flex items-center gap-2 px-1">
            <hr class="bg-soft-silk/20 h-5 w-[3px] rounded-full text-transparent" />
        </div>

        <ControlButton
            :disabled="getNodes.length === 0"
            title="Delete all nodes"
            @click="deleteAllNodes"
        >
            <UiIcon
                name="MaterialSymbolsDeleteRounded"
                class="text-stone-gray absolute shrink-0 scale-125"
            />
        </ControlButton>

        <ControlButton
            :disabled="getNodes.length === 0"
            title="Run all nodes"
            @click="
                setExecutionPlan(props.graphId, DEFAULT_NODE_ID, ExecutionPlanDirectionEnum.ALL)
            "
        >
            <UiIcon name="CodiconRunAll" class="text-stone-gray absolute shrink-0 scale-125" />
        </ControlButton>
    </Controls>
</template>

<style scoped></style>
