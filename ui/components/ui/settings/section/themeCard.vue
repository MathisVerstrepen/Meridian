<script lang="ts" setup>
const props = defineProps<{
    theme: 'light' | 'dark' | 'oled' | 'standard';
}>();
</script>

<template>
    <div class="cursor-pointer transition-transform hover:scale-105">
        <div
            class="bg-obsidian h-28 w-full rounded-lg p-4 shadow-md"
            :class="{
                'theme-light': props.theme === 'light',
                'theme-dark': props.theme === 'dark',
                'theme-oled': props.theme === 'oled',
                'theme-standard': props.theme === 'standard',
            }"
        >
            <h3 class="text-soft-silk mb-2 text-center text-xl font-bold uppercase">
                {{ props.theme }}
            </h3>
            <p class="text-soft-silk text-sm">Preview of the {{ props.theme }} theme.</p>
            <div
                class="bg-anthracite mx-auto mt-4 flex w-fit items-center justify-center gap-2 rounded-lg p-2 shadow-sm"
            >
                <span class="bg-soft-silk h-6 w-6 rounded-lg"></span>
                <span class="bg-stone-gray h-6 w-6 rounded-lg"></span>
                <span class="bg-obsidian h-6 w-6 rounded-lg"></span>
                <span class="bg-ember-glow h-6 w-6 rounded-lg"></span>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
