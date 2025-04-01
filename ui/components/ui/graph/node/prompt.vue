<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { Position, Handle } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

const { getBlockById } = useBlocks();
const blockDefinition = getBlockById('primary-prompt-text');

const props = defineProps<NodeProps>();

const emit = defineEmits(['updateNodeInternals']);
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="blockDefinition?.minSize?.height"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-slate-blue border-slate-blue-dark flex h-full w-full flex-col rounded-xl border-2 p-4 pt-3
            text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{ 'opacity-50': props.dragging }"
    >
        <!-- <p class="text-sm text-obsidian">{{ props.dragging }}</p> -->
        <label class="mb-3 flex w-fit items-center gap-2" :for="'prompt-textarea-' + props.id">
            <Icon
                name="iconoir:input-field"
                style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                class="opacity-80"
            />
            <span class="text-soft-silk/80 -translate-y-[1px] font-bold">
                {{ blockDefinition?.name }}
            </span>
        </label>
        <textarea
            type="text"
            :id="'prompt-textarea-' + props.id"
            v-model="props.data.prompt"
            class="nodrag bg-soft-silk/50 h-full w-full resize-none rounded-lg p-2 focus:ring-0 focus:outline-none"
            placeholder="Enter your prompt here"
        ></textarea>
    </div>

    <Handle
        type="source"
        :position="Position.Bottom"
        style="background: var(--color-slate-blue-dark)"
    />
</template>

<style scoped></style>
