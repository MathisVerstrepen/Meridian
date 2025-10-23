<script lang="ts" setup>
const props = defineProps<{
    title: string;
    usage: {
        billing_period_end: string;
        used: number;
        total: number;
    };
}>();
</script>

<template>
    <div>
        <h4 class="mb-1 font-semibold">{{ props.title }}</h4>
        <div class="bg-anthracite h-2 w-full rounded-full">
            <div
                class="bg-ember-glow h-2 rounded-full"
                :style="{ width: `${(props.usage.used / props.usage.total) * 100}%` }"
            ></div>
        </div>
        <p class="text-stone-gray/80 mt-2 h-2 text-right text-xs">
            {{ props.usage.used }} / {{ props.usage.total }} used
        </p>
    </div>
</template>

<style scoped></style>
