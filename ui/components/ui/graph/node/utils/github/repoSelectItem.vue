<script lang="ts" setup>
import type { Repo } from '@/types/github';

defineProps<{
    repo: Repo;
}>();
</script>

<template>
    <div class="flex items-center justify-between w-full">
        <div class="flex items-center justify-center gap-2">
            <div class="bg-stone-gray/20 flex items-center rounded-full pr-2 pl-1">
                <UiIcon name="MaterialSymbolsLightStarOutlineRounded" class="text-stone-gray h-5 w-5" />
                <span class="text-stone-gray/70 text-xs">{{ repo.stargazers_count }}</span>
            </div>

            <span class="text-stone-gray/70 text-sm">{{ repo.full_name }}</span>
        </div>

        <span
            v-if="repo.private"
            class="bg-golden-ochre/20 text-golden-ochre rounded-full px-2 py-0.5 text-xs"
            >Private</span
        >        
    </div>

</template>

<style scoped></style>
