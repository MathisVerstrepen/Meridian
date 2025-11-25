<script lang="ts" setup>
import type { ModelInfo } from '@/types/model';

defineProps<{
    model: ModelInfo;
    index: number;
    active: boolean;
    selected: boolean;
    pinnedModelsLength: number;
    exactoModelsLength: number;
    mergedModelsLength: number;
}>();

// --- Composables ---
const { formatModelPrice, formatContextLength } = useFormatters();
</script>

<template>
    <li
        :class="{
            'h-10': index !== 0,
            'h-17': index === 0,
            'h-18':
                index === pinnedModelsLength || index === exactoModelsLength + pinnedModelsLength,
        }"
        :title="model.name"
    >
        <!-- Section heading logic: -->
        <div
            v-if="index === 0 && pinnedModelsLength"
            class="bg-anthracite/10 mb-1 flex items-center justify-between rounded-md px-4 py-1
                text-xs font-bold"
        >
            <span class="text-anthracite">Pinned Models</span>
            <span class="text-anthracite/50"> Input $ - Completion $ - Context - Tools</span>
        </div>

        <div
            v-if="
                exactoModelsLength &&
                index === pinnedModelsLength &&
                mergedModelsLength > pinnedModelsLength + exactoModelsLength
            "
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center justify-between
                rounded-md px-4 py-1 text-xs font-bold"
            :class="{
                'mt-1': index !== 0,
            }"
            title="Exacto Models provide higher tool calling accuracy."
        >
            <span class="text-anthracite">Exacto Models</span>
            <span class="text-anthracite/50"> Input $ - Completion $ - Context - Tools</span>
        </div>

        <div
            v-if="
                index === exactoModelsLength + pinnedModelsLength &&
                mergedModelsLength > exactoModelsLength + pinnedModelsLength
            "
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center justify-between
                rounded-md px-4 py-1 text-xs font-bold"
            :class="{
                'mt-1': index !== 0,
            }"
        >
            <span class="text-anthracite">All Models</span>
            <span class="text-anthracite/50"> Input $ - Completion $ - Context - Tools</span>
        </div>

        <div
            class="relative cursor-pointer rounded-md py-2 pr-10 pl-10 select-none"
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
                <span class="truncate">{{ model.name }}</span>
                <span
                    class="shrink-0 text-xs font-normal"
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

            <div
                v-if="model.toolsSupport"
                title="This model supports tools integration"
                class="bg-ember-glow/10 text-ember-glow absolute right-2 bottom-[11px] flex
                    items-center gap-1 rounded-md px-1 py-0.5 text-xs font-medium"
            >
                <UiIcon name="MdiWrenchOutline" class="h-4 w-4" />
            </div>
        </div>
    </li>
</template>

<style scoped></style>
