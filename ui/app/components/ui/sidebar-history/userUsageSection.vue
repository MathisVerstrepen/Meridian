<script lang="ts" setup>
const props = defineProps<{
    title: string;
    usage: {
        billing_period_end: string;
        used: number;
        total: number;
    };
}>();

const percentage = computed(() => {
    if (props.usage.total === 0) return 0;
    return Math.round((props.usage.used / props.usage.total) * 100);
});
</script>

<template>
    <div class="text-sm">
        <div class="mb-1.5 flex items-baseline justify-between">
            <h4 class="text-soft-silk font-semibold">{{ props.title }}</h4>
            <span class="text-stone-gray/90 font-mono text-xs"
                >{{ props.usage.used.toLocaleString() }} /
                {{ props.usage.total.toLocaleString() }}</span
            >
        </div>
        <div class="bg-anthracite/80 relative h-2.5 w-full overflow-hidden rounded-full">
            <div
                class="bg-ember-glow h-full rounded-full transition-all duration-500 ease-out"
                :style="{ width: `${percentage}%` }"
            ></div>
        </div>
        <div class="mt-1.5 flex items-baseline justify-between">
            <p class="text-stone-gray/80 text-xs">
                Resets on
                <NuxtTime :datetime="props.usage.billing_period_end" month="short" day="numeric" />
            </p>
            <p class="text-ember-glow text-xs font-bold">{{ percentage }}% used</p>
        </div>
    </div>
</template>

<style scoped></style>
