<script lang="ts" setup>
import type { Node } from '@vue-flow/core';

defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
    setCurrentModel: (model: string) => void;
}>();
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">Model</h3>
        <UiModelsSelect
            :model="node.data.model"
            :set-model="
                (model: string) => {
                    setCurrentModel(model);
                    setNodeDataKey('model', model);
                }
            "
            :disabled="false"
            to="right"
            variant="grey"
            teleport
        />
    </div>

    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">Tools</h3>
        <div class="flex flex-wrap gap-2 px-1">
            <button
                class="group relative flex h-16 w-32 cursor-pointer flex-col items-center
                    justify-center gap-1 rounded-lg p-2 text-center text-sm font-bold ring-2
                    transition-all duration-200 ease-in-out"
                title="Enable or disable web search for this node."
                :class="[
                    node.data.isWebSearch
                        ? 'bg-ember-glow/10 ring-ember-glow text-ember-glow'
                        : `bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk/80
                            hover:text-soft-silk/90 ring-stone-gray/20 hover:ring-stone-gray/40`,
                ]"
                @click="setNodeDataKey('isWebSearch', !node.data.isWebSearch)"
            >
                <UiIcon name="MdiWeb" class="h-5 w-5" />
                Web Search
            </button>
        </div>
    </div>
</template>

<style scoped></style>
