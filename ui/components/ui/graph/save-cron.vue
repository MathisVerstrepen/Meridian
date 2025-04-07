<script lang="ts" setup>
import { SavingStatus } from '@/types/enums';
import { useVueFlow } from '@vue-flow/core';

const route = useRoute();
const { id } = route.params as { id: string };

const { onNodesChange, onEdgesChange } = useVueFlow('main-graph-' + id);

const sidebarSelectorStore = useSidebarSelectorStore();
const { isOpen } = storeToRefs(sidebarSelectorStore);

const canvasSaveStore = useCanvasSaveStore();

const props = defineProps({
    updateGraphHandler: {
        type: Function as PropType<() => Promise<void>>,
        required: true,
    },
});

onMounted(() => {
    onNodesChange((changes) => {
        if (changes.length === 0) {
            return;
        }
        if (changes.some((change) => change.type === 'select')) {
            return;
        }
        canvasSaveStore.setNeedSave(SavingStatus.NOT_SAVED);
    });

    onEdgesChange((changes) => {
        if (changes.length === 0) {
            return;
        }
        if (changes.some((change) => change.type === 'select')) {
            return;
        }
        canvasSaveStore.setNeedSave(SavingStatus.NOT_SAVED);
    });

    const interval = setInterval(() => {
        if (canvasSaveStore.getNeedSave() === SavingStatus.NOT_SAVED) {
            canvasSaveStore.setNeedSave(SavingStatus.SAVING);
            props.updateGraphHandler().then(() => {
                canvasSaveStore.setNeedSave(SavingStatus.SAVED);
            });
        }
    }, 1000);

    onBeforeUnmount(() => {
        clearInterval(interval);
    });
});
</script>

<template>
    <div
        v-show="canvasSaveStore.getNeedSave() !== SavingStatus.INIT"
        class="bg-anthracite/75 border-stone-gray/10 absolute bottom-2 w-40 rounded-2xl border-2 p-1 shadow-lg
            backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{
            'right-[4rem]': !isOpen,
            'right-[31rem]': isOpen,
        }"
    >
        <div
            v-show="canvasSaveStore.getNeedSave() === SavingStatus.NOT_SAVED"
            class="bg-terracotta-clay/20 flex items-center justify-center space-x-2 rounded-xl px-2 py-1"
        >
            <UiIcon name="MaterialSymbolsErrorCircleRounded" class="text-terracotta-clay h-4 w-4" />
            <span class="text-terracotta-clay text-sm font-bold">Not Saved</span>
        </div>
        <div
            v-show="canvasSaveStore.getNeedSave() === SavingStatus.SAVING"
            class="bg-golden-ochre/20 flex items-center justify-center space-x-2 rounded-xl px-2 py-1"
        >
            <UiIcon name="MaterialSymbolsChangeCircleRounded" class="text-golden-ochre h-4 w-4" />
            <span class="text-golden-ochre text-sm font-bold">Saving</span>
        </div>
        <div
            v-show="canvasSaveStore.getNeedSave() === SavingStatus.SAVED"
            class="bg-olive-grove/20 flex items-center justify-center space-x-2 rounded-xl px-2 py-1"
        >
            <UiIcon name="MaterialSymbolsCheckCircleRounded" class="text-olive-grove h-4 w-4" />
            <span class="text-olive-grove text-sm font-bold">Fully Saved</span>
        </div>
    </div>
</template>

<style scoped></style>
