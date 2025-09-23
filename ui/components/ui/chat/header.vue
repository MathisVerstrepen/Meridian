<script lang="ts" setup>
const emit = defineEmits(['close', 'save']);

defineProps<{
    modelSelectDisabled: boolean;
    isTemporary: boolean;
    isEmpty: boolean;
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
            :set-model="
                (model: string) => {
                    currentModel = model;
                }
            "
            :disabled="modelSelectDisabled"
            to="left"
            variant="grey"
            class="h-10 w-[20rem]"
        />

        <h1 class="flex items-center space-x-3 justify-self-center">
            <UiIcon name="MaterialSymbolsAndroidChat" class="text-stone-gray h-6 w-6" />
            <span class="text-stone-gray font-outfit text-2xl font-bold">Chat</span>
        </h1>

        <!-- Action Buttons -->
        <div class="flex items-center justify-center justify-self-end">
            <!-- Save Button -->
            <button
                v-if="isTemporary && !isEmpty"
                class="hover:bg-obsidian/30 bg-obsidian/20 text-soft-silk/80 flex h-10 w-fit items-center justify-center
                    gap-2 rounded-full p-1 px-4 transition-colors duration-200 ease-in-out hover:cursor-pointer"
                title="Save Conversation"
                @click="emit('save')"
            >
                <UiIcon name="MdiContentSaveOutline" class="text-stone-gray h-5 w-5" />
                <span class="text-stone-gray text-sm font-medium">Save Conversation</span>
            </button>

            <!-- Close Button -->
            <button
                v-if="!isTemporary"
                class="hover:bg-stone-gray/10 flex h-10 w-10 items-center justify-center rounded-full p-1 transition-colors
                    duration-200 ease-in-out hover:cursor-pointer"
                @click="emit('close')"
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>
        </div>
    </div>
</template>

<style scoped></style>
