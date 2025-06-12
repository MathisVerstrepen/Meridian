<script lang="ts" setup>
import type { MessageContentImageURL } from '@/types/graph';

// --- Props ---
defineProps<{
    images: MessageContentImageURL[];
}>();

const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;
</script>

<template>
    <ul class="decoration-none flex w-fit list-none flex-wrap gap-2">
        <li
            v-for="(imageUrl, index) in images"
            :key="index"
            class="text-soft-silk/70 border-stone-gray/30 bg-obsidian relative flex items-center rounded-xl border p-1
                text-sm font-bold transition-colors duration-200"
        >
            <NuxtImg
                :src="`${API_BASE_URL}/static/uploads/${imageUrl.url}`"
                class="h-20 w-20 rounded-lg object-cover"
                height="80"
                width="80"
                loading="lazy"
            />
        </li>
    </ul>
</template>

<style scoped></style>
