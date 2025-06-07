<script lang="ts" setup>
const store = useSidebarCanvasStore();
const { isOpen } = storeToRefs(store);
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute top-2 right-2 z-10 flex h-[calc(100%-1rem)] w-0
            flex-col items-center justify-start rounded-2xl border-2 px-4 py-10 shadow-lg backdrop-blur-md
            transition-[width] duration-200 ease-in-out"
        :class="{
            'w-[30rem]': isOpen,
            'w-[3rem]': !isOpen,
        }"
    >
        <UiGraphSidebarBlocks></UiGraphSidebarBlocks>
    </div>
</template>

<style scoped></style>
