<script lang="ts" setup>
const props = defineProps<{
    value: number;
}>();
</script>

<template>
    <div class="relative flex h-8 grow items-center">
        <div class="progress-track relative h-1 w-full bg-stone-300">
            <div class="dashed-line absolute top-0 left-0 h-full w-full"></div>
            <div
                class="progress-fill relative h-full bg-stone-100 transition-all duration-200 ease-in-out"
                :class="{
                    'progress-fill-active': props.value < 1,
                }"
                :style="{ width: `${props.value * 100}%` }"
            ></div>
        </div>
    </div>
</template>

<style scoped>
@keyframes move-dashes {
    to {
        background-position: 40px 0;
    }
}

@keyframes pulse-glow {
    50% {
        box-shadow: 0 0 0 8px rgba(245, 245, 244, 0);
    }
}

.progress-track::before,
.progress-track::after {
    content: '';
    position: absolute;
    top: 50%;
    z-index: 10;
    transform: translateY(-50%);
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 9999px;
    background-color: var(--color-stone-gray);
}

.progress-track::before {
    left: -1px;
}

.progress-track::after {
    right: -1px;
}

.dashed-line {
    background-image: repeating-linear-gradient(
        to right,
        color-mix(in oklab, var(--color-obsidian) 40%, transparent) 0px,
        color-mix(in oklab, var(--color-obsidian) 40%, transparent) 10px,
        transparent 10px,
        transparent 20px
    );
    background-size: 20px 100%;
    animation: move-dashes 1.5s linear infinite;
}

.progress-fill::after {
    content: '';
    position: absolute;
    top: 50%;
    right: 0;
    z-index: 20;
    transform: translate(50%, -50%);
    width: 1rem;
    height: 1rem;
    border-radius: 9999px;
    background-color: var(--color-soft-silk);
    box-shadow: 0 0 0 0 color-mix(in oklab, var(--color-soft-silk) 70%, transparent);
}

.progress-fill-active::after {
    animation: pulse-glow 2s ease-out infinite;
}
</style>
