<script lang="ts" setup>
import { useVueFlow } from '@vue-flow/core';
import type { FunctionalComponent } from 'vue';

const { id: vueFlowId, viewport } = useVueFlow();

const currentZoom = computed(() => {
    return viewport.value.zoom;
});

const patternAttributes = computed(() => {
    const scaledGap: [number, number] = [20 * currentZoom.value || 1, 20 * currentZoom.value || 1];

    return {
        scaledGap,
        scaledSize: Math.max(currentZoom.value, 0.1),
    };
});

const patternId = toRef(() => `pattern-${vueFlowId}`);

interface DotPatternProps {
    radius: number;
}
const DotPattern: FunctionalComponent<DotPatternProps> = ({ radius }) => {
    return h('circle', {
        cx: Math.max(radius, 0.1),
        cy: Math.max(radius, 0.1),
        r: Math.max(radius, 0.1),
        fill: 'var(--color-stone-gray)',
    });
};

const patternX = computed(() => viewport.value.x % patternAttributes.value.scaledGap[0]);
const patternY = computed(() => viewport.value.y % patternAttributes.value.scaledGap[1]);
</script>

<template>
    <svg class="vue-flow__background vue-flow__container h-full w-full">
        <pattern
            :id="patternId"
            :x="patternX"
            :y="patternY"
            :width="patternAttributes.scaledGap[0]"
            :height="patternAttributes.scaledGap[1]"
            patternUnits="userSpaceOnUse"
        >
            <DotPattern :radius="patternAttributes.scaledSize / 2" />
        </pattern>

        <rect width="100%" height="100%" :fill="`url(#${patternId})`" />
    </svg>
</template>
