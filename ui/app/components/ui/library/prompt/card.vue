<script lang="ts" setup>
import type { PromptTemplate } from '@/types/settings';

defineProps<{
    template: PromptTemplate;
}>();

defineEmits<{
    (e: 'open-edit-modal', template: PromptTemplate): void;
    (e: 'delete-template', templateId: string): void;
}>();
</script>

<template>
    <li
        class="bg-obsidian/50 border-stone-gray/10 hover:border-stone-gray/15 relative flex flex-col
            rounded-2xl border-2 p-5 transition-all duration-200"
    >
        <div class="flex flex-1 flex-col gap-3">
            <h4 class="text-soft-silk text-xl leading-tight font-semibold">
                {{ template.name }}
            </h4>
            <p class="text-stone-gray/70 text-sm leading-relaxed">
                {{ template.description || 'No description provided.' }}
            </p>
        </div>
        <div class="mr-0 ml-auto flex items-center gap-2 pt-2">
            <button
                class="hover:bg-stone-gray/10 text-soft-silk flex cursor-pointer items-center
                    justify-center rounded-xl p-2.5 text-sm font-medium transition-colors"
                @click="$emit('open-edit-modal', template)"
            >
                <UiIcon name="MaterialSymbolsEditRounded" class="xh-4 w-4" />
            </button>
            <button
                class="flex cursor-pointer items-center justify-center rounded-xl p-2.5
                    transition-all duration-200 hover:bg-red-500/10"
                @click="$emit('delete-template', template.id)"
            >
                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5 text-red-400" />
            </button>
        </div>
    </li>
</template>

<style scoped></style>
