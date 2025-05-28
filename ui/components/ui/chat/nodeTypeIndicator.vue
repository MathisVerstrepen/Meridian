<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

defineProps<{
    nodeType: NodeTypeEnum;
}>();
</script>

<template>
    <span
        class="absolute top-0 right-0 h-4 w-8 rounded-tr-xl rounded-bl-lg"
        :class="{
            'bg-terracotta-clay': nodeType === NodeTypeEnum.PARALLELIZATION,
            'bg-olive-grove': nodeType === NodeTypeEnum.TEXT_TO_TEXT,
        }"
    >
    </span>
</template>

<style scoped></style>
