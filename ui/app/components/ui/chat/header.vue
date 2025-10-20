<script lang="ts" setup>
const emit = defineEmits(['close', 'save']);

defineProps<{
    isTemporary: boolean;
    isEmpty: boolean;
}>();
</script>

<template>
    <div class="absolute top-6 z-20 h-0 w-full px-10">
        <!-- Close Button -->
        <button
            v-if="!isTemporary"
            class="hover:bg-stone-gray/10 absolute -top-1 right-6 flex h-10 w-10 items-center
                justify-center rounded-full p-1 transition-colors duration-200 ease-in-out
                hover:cursor-pointer"
            @click="emit('close')"
        >
            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
        </button>

        <!-- Save Button -->
        <button
            v-if="isTemporary && !isEmpty"
            class="hover:bg-obsidian/30 bg-obsidian/20 text-soft-silk/80 absolute -top-1 left-2 flex
                h-10 w-fit items-center justify-center gap-2 rounded-full p-1 px-4 transition-colors
                duration-200 ease-in-out hover:cursor-pointer"
            title="Save Conversation"
            @click="emit('save')"
        >
            <UiIcon name="MdiContentSaveOutline" class="text-stone-gray h-5 w-5" />
            <span class="text-stone-gray text-sm font-medium">Save</span>
        </button>
    </div>
</template>

<style scoped></style>
