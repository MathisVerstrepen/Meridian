<script lang="ts" setup>
import { computed } from 'vue';
import type { Node } from '@vue-flow/core';

import { ContextMergerModeEnum } from '@/types/enums';

const props = defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();

const modes = [
    ContextMergerModeEnum.FULL,
    ContextMergerModeEnum.SUMMARY,
    ContextMergerModeEnum.LAST_N,
];

const positions = {
    [ContextMergerModeEnum.FULL]: 0,
    [ContextMergerModeEnum.SUMMARY]: 1,
    [ContextMergerModeEnum.LAST_N]: 2,
};

// --- Computed properties ---
const currentPosition = computed(
    () => positions[props.node.data.mode as ContextMergerModeEnum] ?? 0,
);

const sliderStyle = computed(() => {
    const position = currentPosition.value;
    return `transform: translateX(calc(${position} * 100%));`;
});

const formatLabel = (mode: string) => {
    return mode.replace('_', ' ');
};
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Context Merging Mode
        </h3>

        <div class="border-stone-gray/20 relative flex h-10 overflow-hidden rounded-xl border-2">
            <div
                class="bg-stone-gray/10 absolute inset-y-0 w-1/3 rounded-lg transition-transform
                    duration-300"
                :style="sliderStyle"
            />

            <div
                v-for="mode in modes"
                :key="mode"
                class="relative z-10 flex flex-1 cursor-pointer items-center justify-center"
                @click="setNodeDataKey('mode', mode)"
            >
                <span
                    class="text-stone-gray text-sm font-medium capitalize transition-colors"
                    :class="{
                        'text-white': node.data.mode === mode,
                    }"
                >
                    {{ formatLabel(mode) }}
                </span>
            </div>
        </div>

        <div class="border-stone-gray/20 h-full rounded-xl border-2">
            <div v-if="node.data.mode === ContextMergerModeEnum.FULL" class="p-4">
                <p class="text-stone-gray text-sm">
                    In <strong>Full</strong> mode, the entire context from all inputs is merged
                    together without any summarization. This mode is ideal when you want to retain
                    all details from the input contexts.
                </p>
                <UiGraphSidebarNodeDataSvgFullModeVisual class="my-4 w-full px-8" />
            </div>
            <div v-else-if="node.data.mode === ContextMergerModeEnum.SUMMARY" class="p-4">
                <p class="text-stone-gray text-sm">
                    In <strong>Summary</strong> mode, the contexts from all inputs are summarized
                    before merging. This helps to condense information and is useful when dealing
                    with large amounts of context data.
                </p>
                <UiGraphSidebarNodeDataSvgSummaryVisual class="my-4 w-full px-6" />
            </div>
            <div v-else-if="node.data.mode === ContextMergerModeEnum.LAST_N" class="p-4">
                <p class="text-stone-gray text-sm">
                    In <strong>Last N</strong> mode, only the most recent N pieces of context from
                    the inputs are merged. This mode is beneficial when recent context is more
                    relevant than older information.
                </p>
                <UiGraphSidebarNodeDataSvgNLastModeVisual class="my-4 w-full px-8" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.transition-transform {
    transition-property: transform;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
