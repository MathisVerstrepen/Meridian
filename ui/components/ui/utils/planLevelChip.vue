<script lang="ts" setup>
defineProps<{
    level: 'free' | 'premium';
}>();
</script>

<template>
    <div
        class="w-fit rounded-lg border-2 px-2 text-xs font-bold"
        :class="{
            'border-stone-gray bg-stone-gray/10 text-stone-gray': level === 'free',
            'border-golden-ochre bg-golden-ochre/10 text-golden-ochre': level === 'premium',
        }"
        :title="level === 'free' ? 'Free Plan' : 'Premium Plan'"
    >
        {{ level === 'free' ? 'Free' : 'Premium' }}
    </div>
</template>

<style scoped></style>
