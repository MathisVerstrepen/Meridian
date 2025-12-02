<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataContextMerger } from '@/types/graph';
import { ContextMergerModeEnum } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode', 'update:unlinkNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const blockDefinition = getBlockById('primary-context-merger');

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataContextMerger>>();

// --- Methods ---
const modeConfig = {
    [ContextMergerModeEnum.FULL]: {
        icon: 'TablerArrowMerge',
        label: 'Full',
        description: 'Complete context',
    },
    [ContextMergerModeEnum.SUMMARY]: {
        icon: 'MynauiSparklesSolid',
        label: 'Summary',
        description: 'Condensed context',
    },
    [ContextMergerModeEnum.LAST_N]: {
        icon: 'MingcuteTimeDurationLine',
        label: 'Last N',
        description: 'Recent context',
    },
};

const changeMode = (mode: ContextMergerModeEnum) => {
    props.data.mode = mode;
    emit('updateNodeInternals');
};

// --- Computed ---
const activeContextIndex = computed(() => {
    return Object.keys(modeConfig).indexOf(props.data.mode as ContextMergerModeEnum);
});
</script>

<template>
    <NodeResizer
        :is-visible="props.selected"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
        :graph-id="graphId"
        :node-id="props.id"
        :selected="props.selected"
        source="input"
        :in-group="props.parentNodeId !== undefined"
        @update:delete-node="emit('update:deleteNode', props.id)"
        @update:unlink-node="emit('update:unlinkNode', props.id)"
    />

    <div
        class="bg-golden-ochre border-golden-ochre-dark relative flex h-full w-full flex-col
            rounded-3xl border-2 p-4 pt-3 shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-golden-ochre-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-3 flex w-full items-center justify-center">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                />
                <span class="dark:text-soft-silk/80 text-anthracite text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
        </div>

        <!-- Block Content -->
        <div class="flex w-full flex-1 items-center justify-center">
            <div
                class="bg-obsidian/10 relative grid w-full grid-cols-3 gap-1 rounded-2xl p-1
                    shadow-inner"
            >
                <!-- Active state background -->
                <div
                    class="from-golden-ochre/30 to-golden-ochre-dark/20 border-golden-ochre/30
                        absolute inset-y-1 rounded-xl border bg-gradient-to-r shadow-lg
                        transition-all duration-300 ease-out"
                    :style="{
                        width: 'calc(100% / 3 - 4px)',
                        left: `calc(${activeContextIndex * 33.333}% + ${4 - activeContextIndex * 2}px)`,
                    }"
                ></div>

                <!-- Mode buttons -->
                <div
                    v-for="(config, mode) in modeConfig"
                    :key="mode"
                    class="relative z-10 flex cursor-pointer items-center justify-center rounded-xl
                        px-3 py-2 transition-all duration-200"
                    :class="{
                        'opacity-70': props.data.mode !== mode,
                        'hover:opacity-100': true,
                    }"
                    @click="changeMode(mode)"
                >
                    <div class="flex flex-col items-center gap-1">
                        <UiIcon
                            :name="config.icon"
                            class="dark:text-soft-silk text-anthracite h-5 w-5"
                            :class="{
                                'font-bold opacity-100': props.data.mode === mode,
                                'opacity-60': props.data.mode !== mode,
                            }"
                        />
                        <span
                            class="dark:text-soft-silk text-anthracite text-xs font-semibold
                                whitespace-nowrap"
                            :class="{
                                'opacity-100': props.data.mode === mode,
                                'opacity-70': props.data.mode !== mode,
                            }"
                        >
                            {{ config.label }}
                        </span>

                        <UiIcon
                            v-if="
                                mode === ContextMergerModeEnum.SUMMARY &&
                                Object.keys(props.data.branch_summaries).length > 0
                            "
                            name="MdiDatabaseOutline"
                            class="dark:text-soft-silk/25 text-anthracite/25 absolute top-1.5
                                right-1.5 h-3 w-3"
                            :class="{
                                'font-bold opacity-100': props.data.mode === mode,
                                'opacity-60': props.data.mode !== mode,
                            }"
                        />
                    </div>
                </div>
            </div>
        </div>
    </div>

    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        type="target"
        :node-id="props.id"
        :options="[]"
        :style="{ left: '50%' }"
        :is-dragging="props.dragging"
        class="handletopcustom"
        multiple-input
    />
    <UiGraphNodeUtilsHandleContext
        :id="props.id"
        :node-id="props.id"
        :options="[]"
        type="source"
        :is-dragging="props.dragging"
    />
</template>

<style>
.handletopcustom > .vue-flow__handle {
    width: 150px !important;
}
</style>
