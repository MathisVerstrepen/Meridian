<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { Position, Handle } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

const props = defineProps<NodeProps>();

const emit = defineEmits(['updateNodeInternals']);
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="400"
        :minHeight="150"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-slate-blue text-black rounded-xl p-4 pt-3 shadow-lg border-2 border-slate-blue-dark w-full h-full flex flex-col transition-all duration-200 ease-in-out"
        :class="{ 'opacity-50': props.dragging }"
    >
        <!-- <p class="text-sm text-obsidian">{{ props.dragging }}</p> -->
        <label class="mb-3 w-fit flex items-center gap-2" :for="'prompt-textarea-' + props.id">
            <Icon
                name="iconoir:input-field"
                style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                class="opacity-80"
            />
            <span class="text-soft-silk/80 font-bold -translate-y-[1px]">Prompt</span>
        </label>
        <textarea
            type="text"
            :id="'prompt-textarea-' + props.id"
            v-model="props.data.prompt"
            class="nodrag w-full rounded-lg focus:outline-none focus:ring-0 resize-none p-2 bg-soft-silk/50 h-full"
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
