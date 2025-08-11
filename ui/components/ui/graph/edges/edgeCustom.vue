<script lang="ts" setup>
import { BaseEdge, getBezierPath } from '@vue-flow/core';
import { computed } from 'vue';
import { type EdgeProps } from '@vue-flow/core';

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
        </g>
    </template>
</template>
