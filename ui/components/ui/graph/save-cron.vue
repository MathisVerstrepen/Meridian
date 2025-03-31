<script lang="ts" setup>
import { SavingStatus } from '@/types/enums';

const props = defineProps({
    updateGraphHandler: {
        type: Function as PropType<() => Promise<void>>,
        required: true,
    },
    setNeedSave: {
        type: Function as PropType<(value: SavingStatus) => void>,
        required: true,
    },
    getNeedSave: {
        type: Function as PropType<() => SavingStatus>,
        required: true,
    },
});

onMounted(() => {
    const interval = setInterval(() => {
        if (props.getNeedSave() === SavingStatus.NOT_SAVED) {
            props.setNeedSave(SavingStatus.SAVING);
            props.updateGraphHandler().then(() => {
                props.setNeedSave(SavingStatus.SAVED);
            });
        }
    }, 1000);

    onBeforeUnmount(() => {
        clearInterval(interval);
    });
});
</script>

<template>
    <Transition name="fade">
        <div
            v-show="props.getNeedSave() !== SavingStatus.INIT"
            class="bg-anthracite/75 backdrop-blur-md rounded-2xl border-2 border-stone-gray/10 shadow-lg w-40 p-1 absolute bottom-4 left-4"
        >
            <div
                v-if="props.getNeedSave() === SavingStatus.NOT_SAVED"
                class="bg-terracotta-clay/20 flex items-center justify-center rounded-xl px-2 py-1 space-x-2"
            >
                <Icon
                    name="material-symbols:error-circle-rounded"
                    style="color: var(--color-terracotta-clay); height: 1rem; width: 1rem"
                    class=""
                />
                <span class="text-terracotta-clay font-bold text-sm">Not Saved</span>
            </div>
            <div
                v-else-if="props.getNeedSave() === SavingStatus.SAVING"
                class="bg-golden-ochre/20 flex items-center justify-center rounded-xl px-2 py-1 space-x-2"
            >
                <Icon
                    name="material-symbols:change-circle-rounded"
                    style="color: var(--color-golden-ochre); height: 1rem; width: 1rem"
                    class=""
                />
                <span class="text-golden-ochre font-bold text-sm">Saving</span>
            </div>
            <div
                v-else
                class="bg-olive-grove/20 flex items-center justify-center rounded-xl px-2 py-1 space-x-2"
            >
                <Icon
                    name="material-symbols:check-circle-rounded"
                    style="color: var(--color-olive-grove); height: 1rem; width: 1rem"
                    class=""
                />
                <span class="text-olive-grove font-bold text-sm">Fully Saved</span>
            </div>
        </div>
    </Transition>
</template>

<style scoped>
.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

.fade-enter-to,
.fade-leave-from {
    opacity: 1;
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}
</style>
