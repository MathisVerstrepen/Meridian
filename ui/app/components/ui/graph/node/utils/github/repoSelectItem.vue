<script lang="ts" setup>
import type { RepositoryInfo } from '@/types/github';

defineProps<{
    repo: RepositoryInfo;
}>();
</script>

<template>
    <div class="flex grow items-center justify-between overflow-hidden">
        <div class="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            <div class="bg-stone-gray/20 flex shrink-0 items-center rounded-full pr-2 pl-1">
                <UiIcon
                    name="MaterialSymbolsLightStarOutlineRounded"
                    class="text-stone-gray h-5 w-5"
                />
                <span class="text-stone-gray/70 text-xs">{{ repo.stargazers_count }}</span>
            </div>

            <p
                class="text-stone-gray/70 min-w-0 overflow-hidden text-sm text-ellipsis whitespace-nowrap"
            >
                {{ repo.full_name }}
            </p>
        </div>
    </div>
</template>

<style scoped></style>