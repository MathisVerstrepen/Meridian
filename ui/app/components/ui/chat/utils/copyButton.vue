<script setup lang="ts">
const props = defineProps<{
    textToCopy: string;
}>();

const copied = ref(false);

// --- Core Logic Functions ---
const copyCode = async () => {
    if (copied.value) return; // Prevent re-triggering while in "copied" state

    const regexThink = /\[THINK\](.*?)\[!THINK\]/gs;
    const regexWebSearch = /\[WEB_SEARCH\](.*?)\[!WEB_SEARCH\]/gs;
    const regexFetchUrl = /<fetch_url>.*?<\/fetch_url>/gs;
    const cleanedText = props.textToCopy
        .replace(regexThink, '')
        .replace(regexWebSearch, '')
        .replace(regexFetchUrl, '');
    await navigator.clipboard.writeText(cleanedText);
    copied.value = true;
    setTimeout(() => {
        copied.value = false;
    }, 2000);
};
</script>

<template>
    <button
        class="hover:bg-soft-silk/5 flex items-center justify-center rounded-full p-2 transition-all
            duration-200 ease-in-out hover:cursor-pointer"
        :aria-label="copied ? 'Copied!' : 'Copy code'"
        v-bind="$attrs"
        @click="copyCode"
    >
        <Transition name="fade-scale" mode="out-in">
            <UiIcon
                v-if="!copied"
                key="copy"
                name="MaterialSymbolsContentCopyOutlineRounded"
                class="text-soft-silk/80 h-5 w-5"
            />
            <UiIcon
                v-else
                key="check"
                name="MaterialSymbolsCheckSmallRounded"
                class="h-5 w-5 text-green-400"
            />
        </Transition>
    </button>
</template>

<style scoped>
.fade-scale-enter-active,
.fade-scale-leave-active {
    transition:
        transform 0.2s ease,
        opacity 0.2s ease;
}

.fade-scale-enter-from,
.fade-scale-leave-to {
    opacity: 0;
    transform: scale(0.8);
}
</style>
