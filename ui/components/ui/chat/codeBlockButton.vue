<script setup lang="ts">
const props = defineProps<{
    rawCode: string;
}>();

const copied = ref(false);

const copyCode = async () => {
    await navigator.clipboard.writeText(props.rawCode);
    copied.value = true;
    setTimeout(() => {
        copied.value = false;
    }, 2000);
};
</script>

<template>
    <button
        class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute -top-1 -right-1 flex h-8 w-8 cursor-pointer
            items-center justify-center rounded-full p-1 backdrop-blur-sm transition-colors duration-200
            ease-in-out"
        @click="copyCode"
        :aria-label="copied ? 'Copied!' : 'Copy code'"
    >
        <UiIcon
            name="MaterialSymbolsContentCopyOutlineRounded"
            class="text-soft-silk/80 h-5 w-5"
            v-if="!copied"
        />
        <UiIcon name="MaterialSymbolsCheckSmallRounded" class="h-6 w-6 text-green-400" v-else />
    </button>
</template>

<style scoped></style>
