<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

defineProps<{
    nodeType: NodeTypeEnum;
}>();
</script>

<template>
    <div
        class="ml-0.5 inline-block rounded-lg border border-transparent px-2 py-0.5 text-xs
            font-medium text-white capitalize"
        :class="{
            'bg-slate-blue/50 border-slate-blue-dark': nodeType === NodeTypeEnum.PROMPT,
            'bg-terracotta-clay/50 border-terracotta-clay-dark':
                nodeType === NodeTypeEnum.PARALLELIZATION,
            'bg-olive-grove/50 border-olive-grove-dark': nodeType === NodeTypeEnum.TEXT_TO_TEXT,
            'bg-sunbaked-sand/50 border-sunbaked-sand-dark': nodeType === NodeTypeEnum.ROUTING,
            'bg-dried-heather/50 border-dried-heather-dark': nodeType === NodeTypeEnum.FILE_PROMPT,
            'bg-github/50 border-github': nodeType === NodeTypeEnum.GITHUB,
        }"
    >
        {{ nodeType }}
    </div>
</template>

<style scoped></style>
