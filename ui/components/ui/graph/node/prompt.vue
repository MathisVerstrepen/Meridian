<script lang="ts" setup>
import { Position, Handle, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import { SavingStatus } from '@/types/enums';
import type { DataPrompt } from '@/types/graph';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const { setNeedSave } = useCanvasSaveStore();
const blockDefinition = getBlockById('primary-prompt-text');

// --- Props ---
const props = defineProps<NodeProps<DataPrompt>>();
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="blockDefinition?.minSize?.height"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-slate-blue border-slate-blue-dark relative flex h-full w-full flex-col rounded-3xl border-2 p-4
            pt-3 text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{ 'opacity-50': props.dragging }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="text-soft-silk h-6 w-6 opacity-80"
                />
                <span class="text-soft-silk/80 -translate-y-0.5 text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
            <div class="flex items-center space-x-2">
                <!-- More Action Button -->
                <UiGraphNodeUtilsActions
                    @update:deleteNode="emit('update:deleteNode', props.id)"
                ></UiGraphNodeUtilsActions>
            </div>
        </div>

        <!-- Block Content -->
        <div class="relative h-full w-full">
            <div
                class="absolute bottom-0 left-0 h-1/4 w-full rounded-b-2xl bg-linear-to-b from-[#49545f]/10
                    to-[#49545f]/100"
            ></div>

            <!-- Expand TextArea button -->
            <button class="absolute right-1 bottom-1 cursor-pointer">
                <UiIcon
                    class="text-soft-silk h-5 w-5 opacity-80"
                    name="MaterialSymbolsExpandContentRounded"
                />
            </button>

            <!-- Prompt Input Area -->
            <textarea
                type="text"
                :id="'prompt-textarea-' + props.id"
                v-model="props.data.prompt"
                class="nodrag nowheel hide-scrollbar text-soft-silk h-full w-full resize-none rounded-2xl bg-[#49545f] px-3
                    py-2 text-sm focus:ring-0 focus:outline-none"
                placeholder="Enter your prompt here"
                @focusout="setNeedSave(SavingStatus.NOT_SAVED)"
                @keypress.enter.prevent="setNeedSave(SavingStatus.NOT_SAVED)"
            ></textarea>
        </div>
    </div>

    <Handle
        type="source"
        :position="Position.Bottom"
        style="background: #b2c7db"
        class="handlebottom"
    />
</template>

<style scoped></style>
