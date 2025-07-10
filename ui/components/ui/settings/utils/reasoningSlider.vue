<script lang="ts" setup>
import { ReasoningEffortEnum } from '@/types/enums';

const props = defineProps<{
    currentReasoningEffort: ReasoningEffortEnum;
}>();

const emits = defineEmits<{
    (event: 'update:reasoningEffort', value: ReasoningEffortEnum): void;
}>();

const positions = {
    [ReasoningEffortEnum.LOW]: 0,
    [ReasoningEffortEnum.MEDIUM]: 1,
    [ReasoningEffortEnum.HIGH]: 2,
};

// --- Computed properties ---
const currentPosition = computed(() => positions[props.currentReasoningEffort]);

const sliderStyle = computed(() => {
    const position = currentPosition.value;
    return `transform: translateX(calc(${position} * 100%));`;
});
</script>

<template>
    <div
        class="border-stone-gray/20 relative flex h-10 overflow-hidden rounded-xl border-2"
        id="canvas-reasoning-effort"
    >
        <div
            class="bg-ember-glow/80 absolute inset-y-0 w-1/3 rounded-lg transition-transform duration-300 ease-in-out"
            :style="sliderStyle"
        ></div>

        <div
            class="relative z-10 flex flex-1 cursor-pointer items-center justify-center"
            @click="emits('update:reasoningEffort', ReasoningEffortEnum.LOW)"
        >
            <span
                class="text-stone-gray text-sm font-medium transition-colors"
                :class="{
                    'text-white': currentReasoningEffort === ReasoningEffortEnum.LOW,
                }"
            >
                Low
            </span>
        </div>

        <div
            class="relative z-10 flex flex-1 cursor-pointer items-center justify-center"
            @click="emits('update:reasoningEffort', ReasoningEffortEnum.MEDIUM)"
        >
            <span
                class="text-stone-gray text-sm font-medium transition-colors"
                :class="{
                    'text-white': currentReasoningEffort === ReasoningEffortEnum.MEDIUM,
                }"
            >
                Medium
            </span>
        </div>

        <div
            class="relative z-10 flex flex-1 cursor-pointer items-center justify-center"
            @click="emits('update:reasoningEffort', ReasoningEffortEnum.HIGH)"
        >
            <span
                class="text-stone-gray text-sm font-medium transition-colors"
                :class="{
                    'text-white': currentReasoningEffort === ReasoningEffortEnum.HIGH,
                }"
            >
                High
            </span>
        </div>
    </div>
</template>

<style scoped>
.transition-transform {
    transition-property: transform;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
