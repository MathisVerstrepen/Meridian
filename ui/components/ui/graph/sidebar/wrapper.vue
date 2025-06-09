<script lang="ts" setup>
import type { Graph } from '@/types/graph';

const store = useSidebarCanvasStore();
const { isOpen } = storeToRefs(store);

defineProps<{
    graph: Graph | null;
}>();
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute top-2 right-2 z-10 flex h-[calc(100%-1rem)] flex-col
            items-center justify-start rounded-2xl border-2 px-4 py-8 shadow-lg backdrop-blur-md
            transition-[width] duration-200 ease-in-out"
        :class="{
            'w-[30rem]': isOpen,
            'w-[3rem]': !isOpen,
        }"
    >
        <HeadlessTabGroup as="div" class="flex h-full w-full flex-col items-center">
            <HeadlessTabList class="mb-6 flex h-14 w-full justify-center space-x-4 overflow-hidden">
                <HeadlessTab
                    class="ui-selected:bg-obsidian/20 text-stone-gray cursor-pointer rounded-xl px-8 py-3 focus:ring-0
                        focus:outline-none"
                >
                    <h1 class="flex items-center space-x-3">
                        <UiIcon name="ClarityBlockSolid" class="h-8 w-8" />
                        <span class="font-outfit text-2xl font-bold">Blocks</span>
                    </h1>
                </HeadlessTab>
                <HeadlessTab
                    class="ui-selected:bg-obsidian/20 text-stone-gray cursor-pointer rounded-xl px-8 py-3 focus:ring-0
                        focus:outline-none"
                >
                    <h1 class="flex items-center space-x-3">
                        <UiIcon name="MaterialSymbolsSettingsRounded" class="h-8 w-8" />
                        <span class="font-outfit text-2xl font-bold">Config</span>
                    </h1>
                </HeadlessTab>
            </HeadlessTabList>

            <HeadlessTabPanels class="h-[calc(100%-1rem-3.5rem)] w-full">
                <HeadlessTabPanel class="h-full w-full">
                    <UiGraphSidebarBlocks></UiGraphSidebarBlocks>
                </HeadlessTabPanel>
                <HeadlessTabPanel class="h-full w-full">
                    <UiGraphSidebarCanvasConfig
                        :graph="graph"
                        v-if="graph"
                    ></UiGraphSidebarCanvasConfig>
                </HeadlessTabPanel>
            </HeadlessTabPanels>
        </HeadlessTabGroup>
    </div>
</template>

<style scoped></style>
