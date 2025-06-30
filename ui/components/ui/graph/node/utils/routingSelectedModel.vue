<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    selectedModel: string;
}>();

// --- Stores ---
const modelStore = useModelStore();

// --- Actions/Methods from Stores ---
const { getModel } = modelStore;
</script>

<template>
    <div
        class="bg-soft-silk/50 border-obsidian/20 text-obsidian/80 relative flex h-full w-full cursor-default
            items-center gap-2 overflow-hidden rounded-2xl border-2 px-3 text-left text-sm focus:outline-none"
    >
        <span class="font-bold opacity-50">To:</span>
        <div class="font-bold">
            <template v-if="props.selectedModel" v-for="model in [getModel(props.selectedModel)]">
                <span
                    v-if="model?.icon"
                    class="flex h-full translate-y-[1px] items-center self-center"
                >
                    <UiIcon :name="'models/' + model.icon" class="h-4 w-4" />
                </span>
                <span class="self-center font-bold capitalize">{{ model.id.split('/')[0] }}</span>
            </template>
            <span v-else class="text-obsidian/50">No model selected</span>
        </div>
    </div>
</template>

<style scoped></style>
