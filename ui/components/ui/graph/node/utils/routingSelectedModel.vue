<script lang="ts" setup>
import type { Route } from '@/types/settings';
// --- Props ---
const props = defineProps<{
    isFetchingModel: boolean;
    selectedRoute: Route | null;
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
        <div class="flex flex-1 grow items-center gap-2 overflow-hidden font-bold">
            <template
                v-if="props.selectedRoute"
                v-for="model in [getModel(props.selectedRoute.modelId)]"
            >
                <span
                    v-if="model?.icon"
                    class="flex h-full translate-y-[1px] items-center self-center"
                >
                    <UiIcon :name="'models/' + model.icon" class="h-4 w-4 -translate-y-[1px]" />
                </span>
                <span class="self-center truncate font-bold capitalize" :title="model?.name">{{
                    model.name
                }}</span>
            </template>
            <span v-else-if="isFetchingModel" class="text-obsidian/50">Selecting model...</span>
            <span v-else class="text-obsidian/50">No model selected</span>
        </div>
    </div>
</template>

<style scoped></style>
