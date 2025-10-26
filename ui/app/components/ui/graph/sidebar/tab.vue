<script lang="ts" setup>
const props = defineProps<{
    name: string;
    icon: string;
}>();
</script>

<template>
    <HeadlessTab
        class="dark:text-stone-gray text-soft-silk/80 relative z-10 flex w-[30%] cursor-pointer
            flex-col items-center justify-center rounded-xl px-3 py-2 focus:ring-0
            focus:outline-none"
    >
        <UiIcon :name="props.icon" class="mt-1 h-6 w-6" />
        <span class="font-outfit text-lg font-bold">{{ props.name }}</span>
    </HeadlessTab>
</template>

<style scoped></style>
