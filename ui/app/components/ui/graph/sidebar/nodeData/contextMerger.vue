<script lang="ts" setup>
import type { Node } from '@vue-flow/core';

import { ContextMergerModeEnum } from '@/types/enums';

const props = defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();

const modes = [
    { value: ContextMergerModeEnum.FULL, icon: 'TablerArrowMerge' },
    { value: ContextMergerModeEnum.SUMMARY, icon: 'MynauiSparklesSolid' },
    { value: ContextMergerModeEnum.LAST_N, icon: 'MingcuteTimeDurationLine' },
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
    <div class="flex flex-col space-y-3">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-2 text-sm font-bold">
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
                :key="mode.value"
                class="relative z-10 flex flex-1 cursor-pointer items-center justify-center gap-1.5"
                @click="setNodeDataKey('mode', mode.value)"
            >
                <UiIcon
                    :name="mode.icon"
                    class="dark:text-soft-silk text-anthracite h-4 w-4"
                    :class="{
                        'font-bold opacity-100': node.data.mode === mode.value,
                        'opacity-60': node.data.mode !== mode.value,
                    }"
                />
                <span
                    class="text-stone-gray text-sm font-medium capitalize transition-colors"
                    :class="{
                        'text-white': node.data.mode === mode.value,
                    }"
                >
                    {{ formatLabel(mode.value) }}
                </span>
            </div>
        </div>

        <div class="bg-obsidian/10 border-stone-gray/20 rounded-xl border p-4">
            <!-- Full Mode -->
            <div v-if="node.data.mode === ContextMergerModeEnum.FULL" class="space-y-4">
                <div class="space-y-2">
                    <h4 class="text-sm font-semibold text-white">Full Context</h4>
                    <p class="text-stone-gray/80 text-sm leading-relaxed">
                        Merges the complete context from all inputs without any summarization.
                    </p>
                    <div class="bg-obsidian/20 rounded-lg p-2">
                        <p class="text-stone-gray/60 text-xs">
                            <span class="text-teal font-medium">Best for:</span> Preserving all
                            details and maintaining complete information integrity.
                        </p>
                    </div>
                </div>
                <div class="flex justify-center">
                    <UiGraphSidebarNodeDataSvgFullModeVisual class="h-64 w-full max-w-xs" />
                </div>
            </div>

            <!-- Summary Mode -->
            <div v-else-if="node.data.mode === ContextMergerModeEnum.SUMMARY" class="space-y-4">
                <div class="space-y-2">
                    <h4 class="text-sm font-semibold text-white">Summarized Context</h4>
                    <p class="text-stone-gray/80 text-sm leading-relaxed">
                        Condenses input contexts through summarization before merging.
                    </p>
                    <div class="bg-obsidian/20 rounded-lg p-2">
                        <p class="text-stone-gray/60 text-xs">
                            <span class="text-teal font-medium">Best for:</span> Processing large
                            amounts of data while retaining key information.
                        </p>
                    </div>
                </div>
                <div class="flex justify-center">
                    <UiGraphSidebarNodeDataSvgSummaryVisual class="h-64 w-full max-w-xs" />
                </div>
            </div>

            <!-- Last N Mode -->
            <div v-else-if="node.data.mode === ContextMergerModeEnum.LAST_N" class="space-y-4">
                <div class="space-y-2">
                    <h4 class="text-sm font-semibold text-white">Last N Contexts</h4>
                    <p class="text-stone-gray/80 text-sm leading-relaxed">
                        Merges only the most recent N pieces of context from inputs.
                    </p>
                    <div class="bg-obsidian/20 rounded-lg p-2">
                        <p class="text-stone-gray/60 text-xs">
                            <span class="text-teal font-medium">Best for:</span> Focusing on recent
                            information when timeliness is crucial.
                        </p>
                    </div>
                </div>
                <div class="flex justify-center">
                    <UiGraphSidebarNodeDataSvgNLastModeVisual class="h-64 w-full max-w-xs" />
                </div>
            </div>
        </div>
    </div>

    <!-- Full Mode Config -->
    <div v-if="node.data?.mode === ContextMergerModeEnum.FULL" class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-2 text-sm font-bold">
            Full Mode Config
        </h3>

        <div class="mt-1 flex w-full items-center justify-between space-x-2 px-2">
            <label for="last-n-input" class="text-stone-gray/80 text-sm">
                Include User Messages:
            </label>
            <UiSettingsUtilsSwitch
                :state="node.data?.include_user_messages ?? true"
                :set-state="
                    (value: boolean) => {
                        setNodeDataKey('include_user_messages', value);
                    }
                "
            />
        </div>
    </div>

    <!-- Last N Config -->
    <div v-if="node.data?.mode === ContextMergerModeEnum.LAST_N" class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-2 text-sm font-bold">
            Last N Config
        </h3>
        <div class="flex w-full items-center justify-between space-x-2 px-2">
            <label for="last-n-input" class="text-stone-gray/80 text-sm">
                Number of Messages to keep:
            </label>
            <UiSettingsUtilsInputNumber
                id="last-n-input"
                class="w-28"
                :number="node.data?.last_n ?? 1"
                placeholder="Default: 1"
                :min="1"
                :step="1"
                @update:number="
                    (value: number) => {
                        setNodeDataKey('last_n', value);
                    }
                "
            />
        </div>

        <div class="mt-2 flex w-full items-center justify-between space-x-2 px-2">
            <label for="last-n-input" class="text-stone-gray/80 text-sm">
                Include User Messages:
            </label>
            <UiSettingsUtilsSwitch
                :state="node.data?.include_user_messages ?? true"
                :set-state="
                    (value: boolean) => {
                        setNodeDataKey('include_user_messages', value);
                    }
                "
            />
        </div>
    </div>

    <!-- Summary reset button -->
    <div v-if="node.data?.mode === ContextMergerModeEnum.SUMMARY" class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-2 text-sm font-bold">
            Summary Config
        </h3>
        <div class="mt-1 flex w-full items-center justify-between space-x-2 px-2">
            <label for="last-n-input" class="text-stone-gray/80 text-sm">
                Clear cached branch summaries:
            </label>
            <button
                class="cursor-pointer rounded-lg bg-red-500/20 px-3 py-1 text-sm font-medium
                    text-red-500 transition-colors duration-200 hover:bg-red-500/30"
                @click="
                    () => {
                        setNodeDataKey('branch_summaries', {});
                    }
                "
            >
                Clear
            </button>
        </div>
    </div>
</template>

<style scoped>
.transition-transform {
    transition-property: transform;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
