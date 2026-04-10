<script lang="ts" setup>
import type { ModelInfo } from '@/types/model';

const props = defineProps<{
    model: ModelInfo;
    index: number;
    active: boolean;
    selected: boolean;
    pinnedModelsLength: number;
    exactoModelsLength: number;
    mergedModelsLength: number;
    hideTool?: boolean;
}>();

// --- Composables ---
const { formatModelPrice, formatContextLength } = useFormatters();

const hasPinnedHeader = computed(() => props.index === 0 && props.pinnedModelsLength > 0);
const hasExactoHeader = computed(
    () =>
        props.exactoModelsLength > 0 &&
        props.index === props.pinnedModelsLength &&
        props.mergedModelsLength > props.pinnedModelsLength + props.exactoModelsLength,
);
const hasAllHeader = computed(
    () =>
        props.index === props.exactoModelsLength + props.pinnedModelsLength &&
        props.mergedModelsLength > props.exactoModelsLength + props.pinnedModelsLength,
);
const rowHeightClass = computed(() => {
    if (hasExactoHeader.value || hasAllHeader.value) {
        return 'h-18';
    }

    if (hasPinnedHeader.value) {
        return 'h-17';
    }

    return 'h-10';
});

const pricingLabel = computed(() => {
    if (props.model.billingType === 'subscription') {
        const formattedContext = formatContextLength(props.model.context_length || 0);
        return formattedContext ? `Subscription - ${formattedContext}` : 'Subscription';
    }

    return [
        formatModelPrice(Number(props.model.pricing.prompt)),
        formatModelPrice(Number(props.model.pricing.completion)),
        formatContextLength(props.model.context_length || 0),
    ].join(' - ');
});
</script>

<template>
    <li :class="rowHeightClass" :title="model.name">
        <!-- Section heading logic: -->
        <div
            v-if="hasPinnedHeader"
            class="bg-anthracite/10 mb-1 flex items-center justify-between rounded-md px-4 py-1
                text-xs font-bold"
        >
            <span class="text-anthracite">Pinned Models</span>
            <span class="text-anthracite/50">
                Input $ - Completion $ - Context<span v-if="!hideTool"> - Tools</span></span
            >
        </div>

        <div
            v-if="hasExactoHeader"
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center justify-between
                rounded-md px-4 py-1 text-xs font-bold"
            :class="{
                'mt-1': index !== 0,
            }"
            title="Exacto Models provide higher tool calling accuracy."
        >
            <span class="text-anthracite">Exacto Models</span>
            <span class="text-anthracite/50">
                Input $ - Completion $ - Context<span v-if="!hideTool"> - Tools</span></span
            >
        </div>

        <div
            v-if="hasAllHeader"
            class="bg-anthracite/10 text-anthracite mb-1 flex items-center justify-between
                rounded-md px-4 py-1 text-xs font-bold"
            :class="{
                'mt-1': index !== 0,
            }"
        >
            <span class="text-anthracite">All Models</span>
            <span class="text-anthracite/50">
                Input $ - Completion $ - Context<span v-if="!hideTool"> - Tools</span></span
            >
        </div>

        <div
            class="relative cursor-pointer rounded-md py-2 pr-10 pl-10 select-none"
            :class="{
                'bg-olive-grove-dark text-soft-silk/80': active,
                'text-obsidian': !active,
                'pr-4!': hideTool,
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
                    {{ pricingLabel }}</span
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
                v-if="model.toolsSupport && !hideTool"
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
