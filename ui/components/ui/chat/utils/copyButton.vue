<script setup lang="ts">
const props = defineProps<{
    textToCopy: string;
}>();

const copied = ref(false);

// --- Core Logic Functions ---
const copyCode = async () => {
    const regex = /\[THINK\](.*?)\[!THINK\]/gs;
    const cleanedText = props.textToCopy.replace(regex, '');
    await navigator.clipboard.writeText(cleanedText);
    copied.value = true;
    setTimeout(() => {
        copied.value = false;
    }, 2000);
};
</script>

<template>
    <button
        class="flex items-center justify-center rounded-full transition-colors duration-200 ease-in-out
            hover:cursor-pointer"
        :aria-label="copied ? 'Copied!' : 'Copy code'"
        v-bind="$attrs"
        @click="copyCode"
    >
        <UiIcon
            v-if="!copied"
            name="MaterialSymbolsContentCopyOutlineRounded"
            class="text-soft-silk/80 h-5 w-5"
        />
        <UiIcon v-else name="MaterialSymbolsCheckSmallRounded" class="h-6 w-6 text-green-400" />
    </button>
</template>

<style scoped></style>
