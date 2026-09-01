<script lang="ts" setup>
import type { TopologyPreviewV1 } from '@/types/graph';

const props = defineProps<{
    preview?: TopologyPreviewV1 | null;
}>();

const renderablePreview = computed(() => {
    const preview = props.preview;

    if (
        preview?.version !== 1 ||
        preview.width !== 1000 ||
        preview.height !== 600 ||
        !Array.isArray(preview.nodes) ||
        !Array.isArray(preview.edges) ||
        preview.nodes.length === 0
    ) {
        return null;
    }

    return preview;
});
</script>

<template>
    <svg
        v-if="renderablePreview"
        class="text-stone-gray pointer-events-none h-full w-full"
        :viewBox="`0 0 ${renderablePreview.width} ${renderablePreview.height}`"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
        focusable="false"
    >
        <line
            v-for="(edge, index) in renderablePreview.edges"
            :key="`edge-${index}`"
            :x1="edge.x1"
            :y1="edge.y1"
            :x2="edge.x2"
            :y2="edge.y2"
            stroke="currentColor"
            stroke-width="5"
            stroke-linecap="round"
            opacity="0.18"
        />
        <rect
            v-for="(node, index) in renderablePreview.nodes"
            :key="`node-${index}`"
            :x="node.x"
            :y="node.y"
            :width="node.width"
            :height="node.height"
            rx="18"
            ry="18"
            fill="currentColor"
            fill-opacity="0.12"
            stroke="currentColor"
            stroke-width="4"
            stroke-opacity="0.2"
        />
    </svg>
</template>
