<script lang="ts" setup>
import type { TopologyPreviewV2 } from '@/types/graph';

const props = defineProps<{
    preview?: TopologyPreviewV2 | null;
}>();

const TARGET_GLYPH_WIDTH = 120;
const TARGET_GLYPH_HEIGHT = 72;
const TARGET_GLYPH_RADIUS = 14;
const TARGET_STROKE_WIDTH = 4;
const MAX_NODES = 64;
const MAX_EDGES = 128;
const EDGE_CENTER_TOLERANCE = 0.5;

type PreviewNode = TopologyPreviewV2['nodes'][number];
type PreviewEdge = TopologyPreviewV2['edges'][number];

interface DisplayNode {
    sourceIndex: number;
    centerX: number;
    centerY: number;
    width: number;
    height: number;
    radius: number;
    strokeWidth: number;
    color: PreviewNode['color'];
}

interface DisplayPreview {
    width: number;
    height: number;
    nodes: DisplayNode[];
    edges: PreviewEdge[];
}

const isValidNode = (node: PreviewNode, viewportWidth: number, viewportHeight: number): boolean =>
    Number.isFinite(node.x) &&
    Number.isFinite(node.y) &&
    Number.isFinite(node.width) &&
    Number.isFinite(node.height) &&
    node.x >= 0 &&
    node.y >= 0 &&
    node.width > 0 &&
    node.height > 0 &&
    node.x + node.width <= viewportWidth &&
    node.y + node.height <= viewportHeight;

const nodesShareCenter = (first: PreviewNode, second: PreviewNode): boolean =>
    first.x + first.width / 2 === second.x + second.width / 2 &&
    first.y + first.height / 2 === second.y + second.height / 2;

const isValidEdge = (edge: PreviewEdge, viewportWidth: number, viewportHeight: number): boolean =>
    Number.isFinite(edge.x1) &&
    Number.isFinite(edge.y1) &&
    Number.isFinite(edge.x2) &&
    Number.isFinite(edge.y2) &&
    edge.x1 >= 0 &&
    edge.x1 <= viewportWidth &&
    edge.x2 >= 0 &&
    edge.x2 <= viewportWidth &&
    edge.y1 >= 0 &&
    edge.y1 <= viewportHeight &&
    edge.y2 >= 0 &&
    edge.y2 <= viewportHeight;

const resolveNodeColor = (color: PreviewNode['color']): string => {
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

const renderablePreview = computed<DisplayPreview | null>(() => {
    const preview = props.preview;

    if (
        preview?.version !== 2 ||
        preview.width !== 1000 ||
        preview.height !== 600 ||
        !Array.isArray(preview.nodes) ||
        !Array.isArray(preview.edges)
    ) {
        return null;
    }

    const sourceNodes: Array<{ node: PreviewNode; sourceIndex: number }> = [];

    for (const [sourceIndex, node] of preview.nodes.slice(0, MAX_NODES).entries()) {
        if (
            isValidNode(node, preview.width, preview.height) &&
            sourceNodes.every(({ node: visibleNode }) => !nodesShareCenter(node, visibleNode))
        ) {
            sourceNodes.push({ node, sourceIndex });
        }
    }

    if (sourceNodes.length < 2) {
        return null;
    }

    // Scale painted bounds, including centered stroke, around the immutable descriptor center.
    const scales = sourceNodes.map(({ node }) => {
        const centerX = node.x + node.width / 2;
        const centerY = node.y + node.height / 2;

        return Math.min(
            1,
            (2 * centerX) / (TARGET_GLYPH_WIDTH + TARGET_STROKE_WIDTH),
            (2 * (preview.width - centerX)) / (TARGET_GLYPH_WIDTH + TARGET_STROKE_WIDTH),
            (2 * centerY) / (TARGET_GLYPH_HEIGHT + TARGET_STROKE_WIDTH),
            (2 * (preview.height - centerY)) / (TARGET_GLYPH_HEIGHT + TARGET_STROKE_WIDTH),
        );
    });

    for (let firstIndex = 0; firstIndex < sourceNodes.length; firstIndex += 1) {
        const first = sourceNodes[firstIndex]!.node;
        const firstCenterX = first.x + first.width / 2;
        const firstCenterY = first.y + first.height / 2;

        for (let secondIndex = firstIndex + 1; secondIndex < sourceNodes.length; secondIndex += 1) {
            const second = sourceNodes[secondIndex]!.node;
            const secondCenterX = second.x + second.width / 2;
            const secondCenterY = second.y + second.height / 2;
            const horizontalScale =
                Math.abs(firstCenterX - secondCenterX) / (TARGET_GLYPH_WIDTH + TARGET_STROKE_WIDTH);
            const verticalScale =
                Math.abs(firstCenterY - secondCenterY) /
                (TARGET_GLYPH_HEIGHT + TARGET_STROKE_WIDTH);
            const pairScale = Math.max(horizontalScale, verticalScale);

            // Both painted half-extents then sum to at most the chosen center clearance.
            scales[firstIndex] = Math.min(scales[firstIndex]!, pairScale);
            scales[secondIndex] = Math.min(scales[secondIndex]!, pairScale);
        }
    }

    const nodes = sourceNodes.map(({ node, sourceIndex }, index): DisplayNode => {
        const scale = scales[index]!;

        return {
            sourceIndex,
            centerX: node.x + node.width / 2,
            centerY: node.y + node.height / 2,
            width: TARGET_GLYPH_WIDTH * scale,
            height: TARGET_GLYPH_HEIGHT * scale,
            radius: TARGET_GLYPH_RADIUS * scale,
            strokeWidth: TARGET_STROKE_WIDTH * scale,
            color: node.color,
        };
    });
    const hasVisibleCenter = (x: number, y: number): boolean =>
        nodes.some(
            (node) =>
                Math.abs(node.centerX - x) <= EDGE_CENTER_TOLERANCE &&
                Math.abs(node.centerY - y) <= EDGE_CENTER_TOLERANCE,
        );
    const edges = preview.edges
        .slice(0, MAX_EDGES)
        .filter(
            (edge) =>
                isValidEdge(edge, preview.width, preview.height) &&
                hasVisibleCenter(edge.x1, edge.y1) &&
                hasVisibleCenter(edge.x2, edge.y2),
        );

    return { width: preview.width, height: preview.height, nodes, edges };
});
</script>

<template>
    <svg
        v-if="renderablePreview"
        class="text-stone-gray pointer-events-none h-full w-full opacity-90 transition-opacity
            duration-200 ease-out group-hover:opacity-100 motion-reduce:transition-none"
        :viewBox="`0 0 ${renderablePreview.width} ${renderablePreview.height}`"
        preserveAspectRatio="xMaxYMid meet"
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
            opacity="0.25"
        />
        <rect
            v-for="node in renderablePreview.nodes"
            :key="`node-${node.sourceIndex}`"
            :x="node.centerX - node.width / 2"
            :y="node.centerY - node.height / 2"
            :width="node.width"
            :height="node.height"
            :rx="node.radius"
            :ry="node.radius"
            :fill="resolveNodeColor(node.color)"
            fill-opacity="0.3"
            :stroke="resolveNodeColor(node.color)"
            :stroke-width="node.strokeWidth"
            stroke-opacity="0.42"
        />
    </svg>
</template>
