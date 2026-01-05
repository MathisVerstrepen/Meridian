<script lang="ts" setup>
import { type ConnectionLineProps, getBezierPath } from '@vue-flow/core';

const props = defineProps<ConnectionLineProps>();

const { snappedHandle } = useEdgeSnapping();

const targetX = computed(() => snappedHandle.value?.position.x ?? props.targetX);
const targetY = computed(() => snappedHandle.value?.position.y ?? props.targetY);

const path = computed(() =>
    getBezierPath({
        sourceX: props.sourceX,
        sourceY: props.sourceY,
        sourcePosition: props.sourcePosition,
        targetX: targetX.value,
        targetY: targetY.value,
        targetPosition: props.targetPosition,
    }),
);
</script>

<template>
    <path
        :d="path[0]"
        fill="none"
        stroke="var(--color-soft-silk)"
        :stroke-width="2.5"
        class="animated opacity-25"
    />
</template>

<style scoped>
.animated {
    stroke-dasharray: 5;
    animation: dashdraw 0.5s linear infinite;
}

@keyframes dashdraw {
    from {
        stroke-dashoffset: 10;
    }
}
</style>
