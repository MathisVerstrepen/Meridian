<script lang="ts" setup>
import { SavingStatus } from '@/types/enums';
import { useVueFlow } from '@vue-flow/core';

// --- Stores ---
const sidebarSelectorStore = useSidebarCanvasStore();
const streamStore = useStreamStore();
const canvasSaveStore = useCanvasSaveStore();

// --- State from Stores (Reactive Refs) ---
const { isRightOpen } = storeToRefs(sidebarSelectorStore);
const { isAnyNodeStreaming } = storeToRefs(streamStore);

// --- Actions/Methods from Stores ---
const { setUpdateGraphHandler, saveGraph, setNeedSave, getNeedSave } = canvasSaveStore;

// --- Routing ---
const route = useRoute();
const { id } = route.params as { id: string };

// --- Composables ---
const { onNodesChange, onEdgesChange, onPaneReady } = useVueFlow('main-graph-' + id);

// --- Props ---
const props = defineProps({
    updateGraphHandler: {
        type: Function as PropType<() => Promise<void>>,
        required: true,
    },
});

let interval: NodeJS.Timeout;

// --- Lifecycle Hooks ---
onPaneReady(async () => {
    await nextTick();

    setUpdateGraphHandler(props.updateGraphHandler);

    onNodesChange((changes) => {
        if (changes.length === 0) {
            return;
        }
        if (changes.some((change) => change.type === 'select')) {
            return;
        }
        setNeedSave(SavingStatus.NOT_SAVED);
    });

    onEdgesChange((changes) => {
        if (changes.length === 0) {
            return;
        }
        if (changes.some((change) => change.type === 'select')) {
            return;
        }
        setNeedSave(SavingStatus.NOT_SAVED);
    });

    interval = setInterval(async () => {
        // Prevent saving if any node is streaming
        if (isAnyNodeStreaming.value) {
            return;
        }

        if (getNeedSave() === SavingStatus.NOT_SAVED) {
            await saveGraph();
        }
    }, 1000);
});

onBeforeUnmount(() => {
    if (interval) {
        clearInterval(interval);
    }
});
</script>

<template>
    <div
        v-show="getNeedSave() !== SavingStatus.INIT"
        class="bg-anthracite/75 border-stone-gray/10 absolute bottom-2 w-40 rounded-2xl border-2 p-1
            shadow-lg backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'right-[4rem]': !isRightOpen,
            'right-[31rem]': isRightOpen,
        }"
    >
        <div
            v-show="getNeedSave() === SavingStatus.NOT_SAVED"
            class="bg-terracotta-clay/20 flex items-center justify-center space-x-2 rounded-xl px-2
                py-1"
        >
            <UiIcon name="MaterialSymbolsErrorCircleRounded" class="text-terracotta-clay h-4 w-4" />
            <span class="text-terracotta-clay text-sm font-bold">Not Saved</span>
        </div>
        <div
            v-show="getNeedSave() === SavingStatus.SAVING"
            class="bg-golden-ochre/20 flex items-center justify-center space-x-2 rounded-xl px-2
                py-1"
        >
            <UiIcon name="MaterialSymbolsChangeCircleRounded" class="text-golden-ochre h-4 w-4" />
            <span class="text-golden-ochre text-sm font-bold">Saving</span>
        </div>
        <div
            v-show="getNeedSave() === SavingStatus.SAVED"
            class="bg-olive-grove/20 flex items-center justify-center space-x-2 rounded-xl px-2
                py-1"
        >
            <UiIcon name="MaterialSymbolsCheckCircleRounded" class="text-olive-grove h-4 w-4" />
            <span class="text-olive-grove text-sm font-bold">Fully Saved</span>
        </div>
    </div>
</template>

<style scoped></style>
