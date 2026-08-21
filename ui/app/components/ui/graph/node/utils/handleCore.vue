<script lang="ts">
export const MAX_HANDLE_HIT_ZONE_SCALE = 3;

export function getHandleHitZoneScale(zoom: number): number {
    if (!Number.isFinite(zoom) || zoom >= 1 || zoom <= 0) {
        return 1;
    }

    return Math.min(1 / zoom, MAX_HANDLE_HIT_ZONE_SCALE);
}
</script>

<script lang="ts" setup>
import { Handle, useVueFlow } from '@vue-flow/core';

defineOptions({ inheritAttrs: false });

const { viewport } = useVueFlow();

const hitZoneStyle = computed(() => ({
    '--handle-hit-zone-scale': getHandleHitZoneScale(viewport.value.zoom),
}));
</script>

<template>
    <Handle v-bind="$attrs" class="zoom-aware-handle" :style="hitZoneStyle" />
</template>

<style scoped>
.zoom-aware-handle::before {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 100%;
    height: 100%;
    content: '';
    transform: translate(-50%, -50%) scale(var(--handle-hit-zone-scale));
}
</style>
