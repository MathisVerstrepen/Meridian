<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

defineProps<{
    nodeType: NodeTypeEnum;
}>();
</script>

<template>
    <span
        class="hover:text-obsidian absolute top-0 right-0 h-4 w-8 cursor-default overflow-hidden rounded-tr-xl
            rounded-bl-lg px-2 text-xs font-bold text-transparent hover:w-fit"
        :class="{
            'bg-terracotta-clay': nodeType === NodeTypeEnum.PARALLELIZATION,
            'bg-olive-grove': nodeType === NodeTypeEnum.TEXT_TO_TEXT,
        }"
    >
        {{ nodeType === NodeTypeEnum.PARALLELIZATION ? 'Parallelization' : 'Text to Text' }}
    </span>
</template>

<style scoped></style>
