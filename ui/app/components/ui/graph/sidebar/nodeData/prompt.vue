<script lang="ts" setup>
import type { Node } from '@vue-flow/core';

defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Original Prompt
        </h3>
        <UiGraphNodeUtilsTextarea
            class="grow"
            :reply="node.data.prompt"
            :readonly="false"
            color="grey"
            placeholder="Enter your prompt here"
            :autoscroll="false"
            :parse-error="false"
            @update:reply="(value: string) => setNodeDataKey('prompt', value)"
        />
    </div>
</template>

<style scoped></style>
