<script lang="ts" setup>
import type { Node, Edge } from "@vue-flow/core";
import { VueFlow, useVueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";

let nodes = ref<Node[]>([]);
let edges = ref<Edge[]>([]);

const { onConnect, addEdges } = useVueFlow();

onConnect((connection) => {
    addEdges(connection);
});

onMounted(() => {
    const graph = document.getElementById("graph");
    const rect = graph?.getBoundingClientRect();
    const centerX = Math.round((rect?.width || 0) / 2 - 160);
    const centerY = Math.round((rect?.height || 0) / 2 - 64);

    nodes = ref<Node[]>([
        {
            id: "1",
            type: "prompt",
            position: { x: centerX, y: 100 },
            data: { prompt: "What is a LLM ? Short Answer" },
        },
        {
            id: "2",
            type: "textToText",
            position: { x: centerX, y: 300 },
            data: { model: "google/gemini-2.0-flash-001" },
        },
    ]);

    edges = ref<Edge[]>([]);
});
</script>

<template>
    <div class="h-4/5 w-4/5 bg-white rounded-lg shadow-lg" id="graph">
        <client-only>
            <VueFlow :nodes="nodes" :edges="edges">
                <Background pattern-color="#aaa" :gap="16" />

                <Controls position="top-left"></Controls>

                <template #node-prompt="promptNodeProps">
                    <UiGraphNodePrompt v-bind="promptNodeProps" />
                </template>
                <template #node-textToText="textToTextNodeProps">
                    <UiGraphNodeTextToText v-bind="textToTextNodeProps" />
                </template>
            </VueFlow>
            <template #fallback>
                <div class="flex items-center justify-center h-full">
                    Loading diagram...
                </div>
            </template>
        </client-only>
    </div>
</template>

<style scoped></style>
