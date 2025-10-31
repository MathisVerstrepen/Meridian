<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

const props = defineProps<{
    nodeType: NodeTypeEnum;
}>();

const { blockDefinitions } = useBlocks();

const block = computed(
    () =>
        blockDefinitions.value.input.find((b) => b.nodeType === props.nodeType) ||
        blockDefinitions.value.generator.find((b) => b.nodeType === props.nodeType),
);
</script>

<template>
    <div
        class="ml-0.5 flex w-fit items-center gap-1 rounded-lg border border-transparent px-1.5
            py-0.5 text-xs font-medium text-white capitalize"
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
        <UiIcon v-if="block" :name="block.icon" class="h-4 w-4" />
        {{ block?.name || 'Unknown' }}
    </div>
</template>

<style scoped></style>
