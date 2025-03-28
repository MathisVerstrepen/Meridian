<script lang="ts" setup>
import type { NodeProps } from "@vue-flow/core";
import { Position, Handle } from "@vue-flow/core";
import { NodeResizer } from "@vue-flow/node-resizer";

const props = defineProps<NodeProps>();

const emit = defineEmits(["updateNodeInternals"]);
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="400"
        :minHeight="150"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-blue-200 text-black rounded-lg p-4 shadow-lg border-2 border-blue-300 w-full h-full flex flex-col"
    >
        <label
            for="prompt-textarea"
            class="block text-sm font-medium text-gray-700 mb-2 flex-shrink-0 w-fit"
        >
            Prompt
        </label>
        <textarea
            type="text"
            id="prompt-textarea"
            v-model="props.data.prompt"
            class="w-full flex-1 min-h-0 rounded-lg focus:outline-none focus:ring-0 resize-none border-2 p-2 border-blue-300/50"
            placeholder="Enter your prompt here"
        ></textarea>
    </div>

    <Handle type="source" :position="Position.Bottom" />
</template>

<style scoped></style>
