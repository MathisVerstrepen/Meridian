<script lang="ts" setup>
import type { Graph } from '@/types/graph';

const sidebarCanvasStore = useSidebarCanvasStore();
const { isOpen } = storeToRefs(sidebarCanvasStore);
const { toggleSidebar } = sidebarCanvasStore;

defineProps<{
    graph: Graph | null;
    isTemporary: boolean;
}>();
</script>

<template>
    <div
        class="dark:bg-anthracite/75 bg-stone-gray/20 border-stone-gray/10 absolute top-2 right-2 z-10 flex
            h-[calc(100%-1rem)] flex-col items-center justify-start rounded-2xl border-2 px-4 py-8 shadow-lg
            backdrop-blur-md transition-[width] duration-200 ease-in-out"
        :class="{
            'w-[30rem]': isOpen,
            'w-[3rem]': !isOpen,
        }"
    >
        <HeadlessTabGroup as="div" class="flex h-full w-full flex-col items-center">
            <HeadlessTabList
                class="mb-6 flex h-14 w-full justify-center space-x-4 overflow-hidden duration-200"
                :class="{ 'pointer-events-none opacity-0': !isOpen }"
            >
                <HeadlessTab
                    v-if="!isTemporary"
                    class="dark:ui-selected:bg-obsidian/20 ui-selected:bg-obsidian/75 dark:text-stone-gray text-soft-silk/80
                        flex cursor-pointer items-center rounded-xl px-8 py-3 focus:ring-0 focus:outline-none"
                >
                    <h1 class="flex items-center space-x-3">
                        <UiIcon name="ClarityBlockSolid" class="h-8 w-8" />
                        <span class="font-outfit text-2xl font-bold">Blocks</span>
                    </h1>
                </HeadlessTab>
                <HeadlessTab
                    class="dark:ui-selected:bg-obsidian/20 ui-selected:bg-obsidian/75 dark:text-stone-gray text-soft-silk/80
                        flex cursor-pointer items-center rounded-xl px-8 py-3 focus:ring-0 focus:outline-none"
                >
                    <h1 class="flex items-center space-x-3">
                        <UiIcon name="MaterialSymbolsSettingsRounded" class="h-8 w-8" />
                        <span class="font-outfit text-2xl font-bold">Config</span>
                    </h1>
                </HeadlessTab>
            </HeadlessTabList>

            <HeadlessTabPanels
                class="h-[calc(100%-1rem-3.5rem)] w-full overflow-hidden duration-200"
                :class="{ 'pointer-events-none opacity-0': !isOpen }"
            >
                <HeadlessTabPanel v-if="!isTemporary" class="h-full w-full">
                    <UiGraphSidebarBlocks />
                </HeadlessTabPanel>
                <HeadlessTabPanel class="h-full w-full">
                    <UiGraphSidebarCanvasConfig v-if="graph" :graph="graph" />
                </HeadlessTabPanel>
            </HeadlessTabPanels>
        </HeadlessTabGroup>

        <div
            class="bg-anthracite hover:bg-obsidian border-stone-gray/10 absolute bottom-1/2 -left-3 flex h-10 w-6
                cursor-pointer items-center justify-center rounded-lg border-2 transition duration-200 ease-in-out"
            role="button"
            @click="toggleSidebar"
        >
            <UiIcon
                name="TablerChevronCompactLeft"
                class="text-stone-gray h-6 w-6"
                :class="{
                    'rotate-180': isOpen,
                }"
            />
        </div>
    </div>
</template>

<style scoped></style>
