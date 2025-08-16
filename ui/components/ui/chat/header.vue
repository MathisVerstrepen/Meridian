<script lang="ts" setup>
const emit = defineEmits(['close']);

const props = defineProps<{
    modelSelectDisabled: boolean;
}>();

// --- Stores ---
const chatStore = useChatStore();

// --- State from Stores (Reactive Refs) ---
const { currentModel } = storeToRefs(chatStore);
</script>

<template>
    <div class="mb-8 grid w-full grid-cols-3 items-center px-10">
        <UiModelsSelect
            :model="currentModel"
            :setModel="
                (model: string) => {
                    currentModel = model;
                }
            "
            :disabled="modelSelectDisabled"
            variant="grey"
            class="h-10 w-[20rem]"
        ></UiModelsSelect>

        <h1 class="flex items-center space-x-3 justify-self-center">
            <UiIcon name="MaterialSymbolsAndroidChat" class="text-stone-gray h-6 w-6" />
            <span class="text-stone-gray font-outfit text-2xl font-bold">Chat</span>
        </h1>

        <!-- Close Button -->
        <button
            class="hover:bg-stone-gray/10 flex h-10 w-10 items-center justify-center justify-self-end rounded-full p-1
                transition-colors duration-200 ease-in-out hover:cursor-pointer"
            @click="emit('close')"
        >
            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
        </button>
    </div>
</template>

<style scoped></style>
