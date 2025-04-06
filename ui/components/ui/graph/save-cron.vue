<script lang="ts" setup>
import { SavingStatus } from '@/types/enums';

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
            backdrop-blur-md transition-all duration-300 ease-in-out"
        :class="{
            'right-[4rem]': !isOpen,
            'right-[31rem]': isOpen,
        }"
    >
        <div
            v-show="canvasSaveStore.getNeedSave() === SavingStatus.NOT_SAVED"
            class="bg-terracotta-clay/20 flex items-center justify-center space-x-2 rounded-xl px-2 py-1"
        >
            <Icon
                name="material-symbols:error-circle-rounded"
                style="color: var(--color-terracotta-clay); height: 1rem; width: 1rem"
            />
            <span class="text-terracotta-clay text-sm font-bold">Not Saved</span>
        </div>
        <div
            v-show="canvasSaveStore.getNeedSave() === SavingStatus.SAVING"
            class="bg-golden-ochre/20 flex items-center justify-center space-x-2 rounded-xl px-2 py-1"
        >
            <Icon
                name="material-symbols:change-circle-rounded"
                style="color: var(--color-golden-ochre); height: 1rem; width: 1rem"
                class=""
            />
            <span class="text-golden-ochre text-sm font-bold">Saving</span>
        </div>
        <div
            v-show="canvasSaveStore.getNeedSave() === SavingStatus.SAVED"
            class="bg-olive-grove/20 flex items-center justify-center space-x-2 rounded-xl px-2 py-1"
        >
            <Icon
                name="material-symbols:check-circle-rounded"
                style="color: var(--color-olive-grove); height: 1rem; width: 1rem"
                class=""
            />
            <span class="text-olive-grove text-sm font-bold">Fully Saved</span>
        </div>
    </div>
</template>

<style scoped></style>
