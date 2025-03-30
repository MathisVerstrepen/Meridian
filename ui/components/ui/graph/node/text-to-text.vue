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
        class="bg-gray-200 text-black rounded-lg p-4 shadow-lg border-2 border-gray-300 w-full h-full flex flex-col"
    >
        <p class="text-sm text-gray-500">{{ props.id }}</p>
        <div class="flex items-center justify-center mb-4 h-fit space-x-1">
            <select
                v-model="props.data.model"
                class="nodrag w-full h-10 p-2 rounded-lg focus:outline-none focus:ring-0 resize-none border-2 border-gray-300"
            >
                <option v-for="option in selectOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                </option>
            </select>

            <button
                @click="sendPrompt"
                :disabled="isLoading || !props.data?.model"
                class="nodrag rounded-lg border-2 border-gray-300 h-10 w-10 flex items-center justify-center flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <Icon
                    v-if="!isLoading"
                    name="lets-icons:send-hor-duotone-line"
                    style="color: black; height: 1.5rem; width: 1.5rem"
                />
                <Icon
                    v-else
                    name="line-md:loading-twotone-loop"
                    style="color: black; height: 1.5rem; width: 1.5rem"
                />
            </button>
        </div>

        <textarea
            v-model="props.data.reply"
            readonly
            class="w-full flex-grow p-2 rounded-lg text-sm focus:outline-none focus:ring-0 resize-none bg-white border-2 border-gray-300 nowheel"
            placeholder="AI response will appear here..."
        ></textarea>
    </div>

    <Handle
        type="target"
        :position="Position.Top"
        :id="'prompt_' + props.id"
        style="left: 33%; background: dodgerblue"
    />
    <Handle
        type="target"
        :position="Position.Top"
        :id="'context_' + props.id"
        style="left: 66%; background: darkorange"
    />
    <Handle type="source" :position="Position.Bottom" style="background: darkorange" />
</template>

<style scoped></style>
