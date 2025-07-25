<script lang="ts" setup>
defineProps<{
    startTime: number;
    selectedCategories: Record<string, boolean>;
}>();
</script>

<template>
    <div class="my-2 flex items-center justify-between gap-2 px-2">
        <NuxtTime :datetime="startTime" relative class="text-soft-silk/50 text-xs font-bold" />

        <div class="flex items-center gap-2">
            <button
                class="bg-stone-gray/20 border-stone-gray/50 h-4 w-8 flex-shrink-0 cursor-pointer items-center
                    justify-center rounded-full border-2 transition-all duration-200 ease-in-out"
                @click="selectedCategories.not_started = !selectedCategories.not_started"
                :class="{
                    '!bg-stone-gray !border-transparent': selectedCategories.not_started,
                }"
                title="Toggle Not Started"
            ></button>
            <button
                class="bg-slate-blue/20 border-slate-blue/50 h-4 w-8 flex-shrink-0 cursor-pointer items-center
                    justify-center rounded-full border-2 transition-all duration-200 ease-in-out"
                @click="selectedCategories.in_progress = !selectedCategories.in_progress"
                :class="{
                    '!bg-slate-blue !border-transparent': selectedCategories.in_progress,
                }"
                title="Toggle In Progress"
            ></button>
            <button
                class="bg-olive-grove/20 border-olive-grove/50 h-4 w-8 flex-shrink-0 cursor-pointer items-center
                    justify-center rounded-full border-2 transition-all duration-200 ease-in-out"
                @click="selectedCategories.done = !selectedCategories.done"
                :class="{
                    '!bg-olive-grove !border-transparent': selectedCategories.done,
                }"
                title="Toggle Done"
            ></button>
        </div>
    </div>
</template>

<style scoped></style>
