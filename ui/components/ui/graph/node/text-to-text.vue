<script lang="ts" setup>
import type { NodeProps } from "@vue-flow/core";
import { Position, Handle } from "@vue-flow/core";
import { NodeResizer } from "@vue-flow/node-resizer";

const props = defineProps<NodeProps>();

const emit = defineEmits(["updateNodeInternals"]);

const selectOptions = [
    { value: "google/gemini-2.0-flash-001", label: "Gemini 2.0 Flash" },
    { value: "deepseek/deepseek-chat-v3-0324", label: "DeepSeek Chat V3" },
    { value: "deepseek/deepseek-r1", label: "DeepSeek R1" },
];
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="400"
        :minHeight="150"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-gray-200 text-black rounded-lg p-4 shadow-lg border-2 border-gray-300 w-full h-full flex flex-col"
    >
        <div class="flex items-center justify-center mb-4 h-fit space-x-1">
            <select
                v-model="props.data.model"
                class="w-full h-10 p-2 rounded-lg focus:outline-none focus:ring-0 resize-none border-2 border-gray-300"
            >
                <option
                    v-for="option in selectOptions"
                    :key="option.value"
                    :value="option.value"
                >
                    {{ option.label }}
                </option>
            </select>

            <button
                class="rounded-lg border-2 border-gray-300 h-10 w-10 flex items-center justify-center"
            >
                <Icon
                    name="lets-icons:send-hor-duotone-line"
                    style="color: black; height: 2rem; width: 2rem"
                />
            </button>
        </div>

        <textarea
            type="text"
            v-model="props.data.reply"
            class="w-full h-52 p-2 rounded-lg focus:outline-none focus:ring-0 resize-none bg-white"
        ></textarea>
    </div>

    <Handle type="target" :position="Position.Top" />
    <Handle type="source" :position="Position.Bottom" />
</template>

<style scoped></style>
