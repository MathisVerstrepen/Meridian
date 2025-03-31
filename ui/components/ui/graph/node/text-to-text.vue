<script lang="ts" setup>
import { Position, Handle, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { GenerateRequest } from '@/types/chat';

const route = useRoute();
const { id } = route.params as { id: string };

const { getGenerateStream } = useAPI();

const props = defineProps<NodeProps>();

const emit = defineEmits(['updateNodeInternals']);

const selectOptions = [
    { value: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
    { value: 'deepseek/deepseek-chat-v3-0324', label: 'DeepSeek Chat V3' },
    { value: 'deepseek/deepseek-r1', label: 'DeepSeek R1' },
];

const isLoading = ref(false);

function addChunk(chunk: string) {
    if (props.data) {
        props.data.reply += chunk;
    }
}

async function sendPrompt() {
    if (!props.data) return;

    isLoading.value = true;
    props.data.reply = '';

    getGenerateStream(
        {
            graph_id: id,
            node_id: props.id,
            model: props.data.model,
        } as GenerateRequest,
        addChunk,
    ).then(() => {
        isLoading.value = false;
    });
}
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="500"
        :minHeight="300"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-olive-grove text-black rounded-xl p-4 pt-3 shadow-lg border-2 border-olive-grove-dark w-full h-full flex flex-col"
    >
        <!-- <p class="text-sm text-gray-500">{{ props.id }}</p> -->
        <label class="mb-3 w-fit flex items-center gap-2">
            <Icon
                name="fluent:code-text-16-filled"
                style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                class="opacity-80"
            />
            <span class="text-soft-silk/80 font-bold -translate-y-[1px]">Text to Text</span>
        </label>
        <div class="flex items-center justify-center mb-4 h-fit space-x-1">
            <select
                v-model="props.data.model"
                class="nodrag w-full h-10 px-4 rounded-lg focus:outline-none focus:ring-0 bg-olive-grove-dark text-soft-silk/80 font-bold"
            >
                <option v-for="option in selectOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                </option>
            </select>

            <button
                @click="sendPrompt"
                :disabled="isLoading || !props.data?.model"
                class="nodrag rounded-lg bg-olive-grove-dark h-10 w-10 flex items-center justify-center flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed
                hover:bg-olive-grove-dark/80 transition-all duration-200 ease-in-out"
            >
                <Icon
                    v-if="!isLoading"
                    name="lets-icons:send-hor-duotone-line"
                    style="color: var(--color-soft-silk); height: 1.75rem; width: 1.75rem"
                    class="opacity-80"
                />
                <Icon
                    v-else
                    name="line-md:loading-twotone-loop"
                    style="color: var(--color-soft-silk); height: 1.5rem; width: 1.5rem"
                    class="opacity-80"
                />
            </button>
        </div>

        <textarea
            v-model="props.data.reply"
            readonly
            class="w-full flex-grow p-2 rounded-lg text-sm focus:outline-none focus:ring-0 resize-none bg-soft-silk/50 nowheel"
            placeholder="AI response will appear here..."
        ></textarea>
    </div>

    <Handle
        type="target"
        :position="Position.Top"
        :id="'prompt_' + props.id"
        style="left: 33%; background: var(--color-slate-blue-dark)"
    />
    <Handle
        type="target"
        :position="Position.Top"
        :id="'context_' + props.id"
        style="left: 66%; background: var(--color-golden-ochre)"
    />
    <Handle type="source" :position="Position.Bottom" style="background: var(--color-golden-ochre)" />
</template>

<style scoped></style>
