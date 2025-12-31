<script lang="ts" setup>
const props = withDefaults(
    defineProps<{
        title: string;
        usage: {
            billing_period_end?: string;
            used: number;
            total: number;
        };
        unit?: 'number' | 'bytes';
    }>(),
    {
        unit: 'number',
    },
);

const { formatFileSize } = useFormatters();

const percentage = computed(() => {
    if (props.usage.total === 0) return 100;
    return Math.round((props.usage.used / props.usage.total) * 100);
});

const isDepleted = computed(() => {
    if (props.usage.total === 0) return true;
    return props.usage.used >= props.usage.total;
});

const formattedUsed = computed(() => {
    if (props.unit === 'bytes') return formatFileSize(props.usage.used);
    return props.usage.used.toLocaleString();
});

const formattedTotal = computed(() => {
    if (props.unit === 'bytes') return formatFileSize(props.usage.total);
    return props.usage.total.toLocaleString();
});

const statusText = computed(() => {
    if (isDepleted.value) {
        return props.unit === 'bytes' ? 'Storage full' : 'Credit depleted';
    }
    return `${percentage.value}% used`;
});
</script>

<template>
    <div class="text-sm">
        <div class="mb-1.5 flex items-baseline justify-between">
            <h4 class="text-soft-silk font-semibold">{{ props.title }}</h4>
            <span
                class="font-mono text-xs"
                :class="isDepleted ? 'text-red-400' : 'text-stone-gray/90'"
            >
                {{ formattedUsed }} / {{ formattedTotal }}
            </span>
        </div>
        <div class="bg-anthracite/80 relative h-2.5 w-full overflow-hidden rounded-full">
            <div
                class="h-full rounded-full transition-all duration-500 ease-out"
                :class="isDepleted ? 'bg-red-500' : 'bg-ember-glow'"
                :style="{ width: `${percentage}%` }"
            ></div>
        </div>
        <div class="mt-1.5 flex items-baseline justify-between">
            <p class="text-stone-gray/80 text-xs">
                <span v-if="props.usage.billing_period_end">
                    Resets on
                    <NuxtTime
                        :datetime="props.usage.billing_period_end"
                        month="short"
                        day="numeric"
                    />
                </span>
                <span v-else-if="props.unit === 'bytes'"> File uploads & generated images </span>
            </p>
            <p class="text-xs font-bold" :class="isDepleted ? 'text-red-400' : 'text-ember-glow'">
                {{ statusText }}
            </p>
        </div>
    </div>
</template>

<style scoped></style>
