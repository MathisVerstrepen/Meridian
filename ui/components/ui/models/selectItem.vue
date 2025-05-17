<script lang="ts" setup>
import type { ModelInfo } from '@/types/model';

defineProps<{
    model: ModelInfo;
    index: number;
    active: boolean;
    selected: boolean;
    pinnedModelsLength: number;
    mergedModelsLength: number;
}>();
</script>

<template>
    <li
        :class="{
            'h-10': index !== 0 && index !== pinnedModelsLength,
            'h-17': index === 0,
            'h-18': index === pinnedModelsLength,
        }"
    >
        <!-- Section heading logic: -->
        <div
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center rounded-md px-4 py-1 text-xs font-bold"
            v-if="index === 0 && pinnedModelsLength"
        >
            Pinned Models
        </div>

        <div
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center rounded-md px-4 py-1 text-xs font-bold"
            :class="{
                'mt-1': index !== 0,
            }"
            v-if="index === pinnedModelsLength && mergedModelsLength > pinnedModelsLength"
        >
            All Models
        </div>

        <div
            class="relative cursor-pointer rounded-md py-2 pr-4 pl-10 select-none"
            :class="{
                'bg-olive-grove-dark text-soft-silk/80': active,
                'text-obsidian': !active,
            }"
        >
            <span
                class="block truncate"
                :class="{
                    'font-medium': selected,
                    'font-normal': !selected,
                }"
            >
                {{ model.name }}
            </span>
            <span
                v-if="model.icon"
                class="absolute inset-y-0 left-0 flex items-center pl-2"
                :class="{
                    'text-soft-silk/80': active,
                    'text-obsidian': !active,
                }"
            >
                <UiIcon :name="'models/' + model.icon" class="h-5 w-5" />
            </span>
        </div>
    </li>
</template>

<style scoped></style>
