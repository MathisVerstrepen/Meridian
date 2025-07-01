<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';

const props = defineProps<{
    nodeType: NodeTypeEnum;
}>();

const nodeTypeLabel = computed(() => {
    switch (props.nodeType) {
        case NodeTypeEnum.PARALLELIZATION:
            return 'Parallelization';
        case NodeTypeEnum.TEXT_TO_TEXT:
            return 'Text to Text';
        case NodeTypeEnum.ROUTING:
            return 'Routing';
        default:
            return '';
    }
});
</script>

<template>
    <span
        class="hover:text-obsidian absolute top-0 right-0 h-4 w-8 cursor-default overflow-hidden rounded-tr-xl
            rounded-bl-lg px-2 text-xs font-bold text-transparent hover:w-fit"
        :class="{
            'bg-terracotta-clay': nodeType === NodeTypeEnum.PARALLELIZATION,
            'bg-olive-grove': nodeType === NodeTypeEnum.TEXT_TO_TEXT,
            'bg-sunbaked-sand-dark': nodeType === NodeTypeEnum.ROUTING,
        }"
    >
        {{ nodeTypeLabel }}
    </span>
</template>

<style scoped></style>
