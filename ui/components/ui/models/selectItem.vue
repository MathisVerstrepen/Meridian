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

// --- Composables ---
const { formatModelPrice, formatContextLength } = useFormatters();
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
            class="bg-anthracite/10 mb-1 flex items-center justify-between rounded-md px-4 py-1 text-xs font-bold"
            v-if="index === 0 && pinnedModelsLength"
        >
            <span class="text-anthracite">Pinned Models</span>
            <span class="text-anthracite/50"> Input $ - Completion $ - Context </span>
        </div>

        <div
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center justify-between rounded-md px-4 py-1 text-xs
                font-bold"
            :class="{
                'mt-1': index !== 0,
            }"
            v-if="index === pinnedModelsLength && mergedModelsLength > pinnedModelsLength"
        >
            <span class="text-anthracite">All Models</span>
            <span class="text-anthracite/50"> Input $ - Completion $ - Context </span>
        </div>

        <div
            class="relative cursor-pointer rounded-md py-2 pr-4 pl-10 select-none"
            :class="{
                'bg-olive-grove-dark text-soft-silk/80': active,
                'text-obsidian': !active,
            }"
        >
            <div
                class="flex w-full items-center justify-between"
                :class="{
                    'font-medium': selected,
                    'font-normal': !selected,
                }"
            >
                {{ model.name.length > 50 ? model.name.slice(0, 50) + '...' : model.name }}
                <span
                    class="text-xs font-normal"
                    :class="{
                        'text-soft-silk/80': active,
                        'text-anthracite': !active,
                    }"
                >
                    {{ formatModelPrice(Number(model.pricing.prompt)) }} -
                    {{ formatModelPrice(Number(model.pricing.completion)) }} -
                    {{ formatContextLength(model.context_length || 0) }}</span
                >
            </div>
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
