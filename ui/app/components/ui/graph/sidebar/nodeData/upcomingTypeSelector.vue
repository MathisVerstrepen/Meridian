<script lang="ts" setup>
import type { NodeTypeEnum } from '@/types/enums';

defineProps<{
    modelValue: NodeTypeEnum;
}>();

const emit = defineEmits(['update:modelValue']);

const { blockDefinitions } = useBlocks();
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h2 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Node Type
        </h2>
        <div class="flex items-center gap-3 px-1">
            <button
                v-for="block in blockDefinitions.generator"
                :key="block.id"
                class="group relative flex h-16 w-32 cursor-pointer flex-col items-center
                    justify-center gap-1 rounded-lg p-2 text-center text-sm font-bold ring-2
                    transition-all duration-200 ease-in-out"
                :class="{
                    'bg-ember-glow/10 ring-ember-glow text-ember-glow':
                        modelValue === block.nodeType,
                    [`bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk/80
                    hover:text-soft-silk/90 ring-stone-gray/20 hover:ring-stone-gray/40`]:
                        modelValue !== block.nodeType,
                }"
                @click="emit('update:modelValue', block.nodeType)"
            >
                <UiIcon :name="block.icon" class="h-5 w-5" />
                <span class="capitalize">{{ block.name }}</span>
            </button>
        </div>
    </div>
</template>

<style scoped></style>
