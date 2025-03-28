<script lang="ts" setup>
import type { Connection } from "@vue-flow/core";
import { VueFlow, useVueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";

const { onConnect, addEdges, vueFlowRef } = useVueFlow();

const { nodes, edges } = useGraphInitializer(vueFlowRef);

const { onDragOver, onDrop } = useGraphDragAndDrop();

onConnect((connection: Connection) => {
    addEdges(connection);
});
</script>

<template>
    <div class="flex items-center justify-center h-full w-full relative">
        <div
            class="h-full w-full rounded-lg shadow-lg bg-white"
            id="graph-container"
            @dragover="onDragOver"
            @drop="onDrop"
        >
            <client-only>
                <VueFlow
                    :nodes="nodes"
                    :edges="edges"
                    :fit-view-on-init="false"
                    class="rounded-lg"
                >
                    <Background pattern-color="#aaa" :gap="16" />
                    <Controls position="top-left" />

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

        <UiGraphSidebarSelector />
    </div>
</template>

<style scoped></style>
