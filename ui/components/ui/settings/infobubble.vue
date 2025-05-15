<script lang="ts" setup>
const open = ref(false);
</script>

<template>
    <HeadlessPopover class="relative">
        <HeadlessPopoverButton
            as="div"
            class="flex h-6 w-6 cursor-pointer items-center justify-center"
            @mouseover="open = true"
            @mouseleave="open = false"
        >
            <UiIcon name="MaterialSymbolsInfoRounded" class="text-stone-gray h-4 w-4" />
        </HeadlessPopoverButton>

        <div v-if="open">
            <HeadlessPopoverPanel
                static
                class="bg-anthracite/75 text-stone-gray absolute z-10 flex w-[500px] flex-col items-start rounded-lg p-4
                    shadow-lg backdrop-blur-md"
            >
                <slot name="default"></slot>
            </HeadlessPopoverPanel>
        </div>
    </HeadlessPopover>
</template>

<style scoped></style>
