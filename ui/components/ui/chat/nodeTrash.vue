<script lang="ts" setup>
defineProps<{
    isHoverDelete: boolean;
}>();
</script>

<template>
    <div
        class="bg-terracotta-clay/20 border-terracotta-clay/25 absolute bottom-2 left-[29.5rem] z-10 h-12 w-12
            rounded-2xl border-2 shadow-lg backdrop-blur-md transition-all duration-200 ease-in-out"
        :class="{ 'border-terracotta-clay/50 h-16 w-16 rounded-3xl': isHoverDelete }"
    >
        <div class="node-trash absolute bottom-0 left-0 z-20 h-32 w-32"/>
        <button
            type="button"
            aria-label="Open Chat"
            class="z-0 flex h-full w-full items-center justify-center"
        >
            <UiIcon
                name="MaterialSymbolsDeleteRounded"
                class="text-terracotta-clay h-6 w-6 transition-all duration-200 ease-in-out"
                :class="{ 'h-8 w-8': isHoverDelete }"
            />
        </button>
    </div>
</template>

<style scoped></style>
