<script lang="ts" setup>
import type { TopologyPreviewColorToken, TopologyPreviewV2 } from '@/types/graph';

const props = defineProps<{
    preview?: TopologyPreviewV2 | null;
}>();

const resolveNodeColor = (color: TopologyPreviewColorToken): string => {
    switch (color) {
        case 'slate-blue':
            return 'var(--color-slate-blue)';
        case 'dried-heather':
            return 'var(--color-dried-heather)';
        case 'github':
            return 'var(--color-github)';
        case 'olive-grove':
            return 'var(--color-olive-grove)';
        case 'terracotta-clay':
            return 'var(--color-terracotta-clay)';
        case 'sunbaked-sand-dark':
            return 'var(--color-sunbaked-sand-dark)';
        case 'golden-ochre':
            return 'var(--color-golden-ochre)';
        case 'stone-gray':
        default:
            return 'var(--color-stone-gray)';
    }
};

const renderablePreview = computed(() => {
    const preview = props.preview;

    if (
        preview?.version !== 2 ||
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
            :fill="resolveNodeColor(node.color)"
            fill-opacity="0.12"
            :stroke="resolveNodeColor(node.color)"
            stroke-width="4"
            stroke-opacity="0.2"
        />
    </svg>
</template>
