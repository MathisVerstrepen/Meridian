<script lang="ts" setup>
import { BaseEdge, getBezierPath, EdgeLabelRenderer, type EdgeProps } from '@vue-flow/core';

const emit = defineEmits(['update:removeEdges']);

const props = defineProps<EdgeProps>();

const path = computed(() => getBezierPath(props));

const isHovered = ref(false);

const { mapHandleIdToNodeType, mapNodeTypeToColor } = graphMappers();
</script>

<template>
    <template v-for="color in [mapNodeTypeToColor(mapHandleIdToNodeType(props.targetHandleId))]">
        <g @mouseenter="isHovered = true" @mouseleave="isHovered = false">
            <BaseEdge
                :id="id"
                :style="{
                    ...props.style,
                    stroke: color,
                    strokeWidth: 6,
                    opacity: isHovered || props.selected ? 1 : 0.5,
                    transition: 'opacity 0.2s',
                }"
                :path="path[0]"
            />

            <EdgeLabelRenderer v-if="props.selected || isHovered">
                <div
                    :style="{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${path[1]}px,${path[2]}px)`,
                        pointerEvents: 'all',
                    }"
                    class="nodrag nopan"
                    @mouseenter="isHovered = true"
                    @mouseleave="isHovered = false"
                >
                    <button
                        class="text-obsidian flex h-5 w-5 cursor-pointer items-center justify-center rounded-full border text-sm
                            font-bold backdrop-blur-2xl transition-transform duration-200 ease-in-out hover:scale-110"
                        :style="{
                            backgroundColor: `color-mix(in oklab, ${color} 50%, transparent)`,
                            borderColor: `color-mix(in oklab, ${color} 50%, transparent)`,
                        }"
                        @click="$emit('update:removeEdges', props.id)"
                    >
                        ×
                    </button>
                </div>
            </EdgeLabelRenderer>
        </g>
    </template>
</template>
