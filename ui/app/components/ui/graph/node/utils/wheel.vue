<script lang="ts" setup>
import type { WheelSlot } from '@/types/settings';

const emit = defineEmits(['update:isHovering']);

// --- Props ---
const props = defineProps<{
    nodeId: string;
    options: WheelSlot[];
    isHovering: boolean;
}>();

// --- Local State ---
const isCtrlPressed = ref(false);
const hoveredIndex = ref<number | null>(null);

// --- Composables ---
const graphEvents = useGraphEvents();
const { getBlockByNodeType } = useBlocks();

// --- Constants ---
const RADIUS = 120;
const INNER_RADIUS = 40;
const VIEWBOX_WIDTH = 260;
const VIEWBOX_HEIGHT = 140;
const CENTER_X = VIEWBOX_WIDTH / 2;
const CENTER_Y = -15;

// --- Computed Properties ---
const filteredOptions = computed(() => {
    return props.options.filter((option) => option.mainBloc);
});

const isMenuVisible = computed(
    () => props.isHovering && isCtrlPressed.value && filteredOptions.value.length > 0,
);

const sectors = computed(() => {
    const count = filteredOptions.value.length;
    if (count === 0) return [];

    const startAngle = 0;
    const totalAngle = 180;
    const anglePerSlice = totalAngle / count;

    return filteredOptions.value.map((option, index) => {
        const startDeg = startAngle + index * anglePerSlice;
        const endDeg = startDeg + anglePerSlice;

        const toRad = (deg: number) => (deg * Math.PI) / 180;

        // Calculate path points
        // Outer Arc Start
        const p1Outer = {
            x: CENTER_X + RADIUS * Math.cos(toRad(startDeg)),
            y: CENTER_Y + RADIUS * Math.sin(toRad(startDeg)),
        };
        // Outer Arc End
        const p2Outer = {
            x: CENTER_X + RADIUS * Math.cos(toRad(endDeg)),
            y: CENTER_Y + RADIUS * Math.sin(toRad(endDeg)),
        };
        // Inner Arc End
        const p1Inner = {
            x: CENTER_X + INNER_RADIUS * Math.cos(toRad(endDeg)),
            y: CENTER_Y + INNER_RADIUS * Math.sin(toRad(endDeg)),
        };
        // Inner Arc Start
        const p2Inner = {
            x: CENTER_X + INNER_RADIUS * Math.cos(toRad(startDeg)),
            y: CENTER_Y + INNER_RADIUS * Math.sin(toRad(startDeg)),
        };

        // Construct Path:
        const path = [
            `M ${p2Inner.x} ${p2Inner.y}`,
            `L ${p1Outer.x} ${p1Outer.y}`,
            `A ${RADIUS} ${RADIUS} 0 0 1 ${p2Outer.x} ${p2Outer.y}`,
            `L ${p1Inner.x} ${p1Inner.y}`,
            `A ${INNER_RADIUS} ${INNER_RADIUS} 0 0 0 ${p2Inner.x} ${p2Inner.y}`,
            'Z',
        ].join(' ');

        // Icon Position Calculation
        const midDeg = startDeg + anglePerSlice / 2;
        const iconRadius = (INNER_RADIUS + RADIUS) / 2;
        const iconX = CENTER_X + iconRadius * Math.cos(toRad(midDeg));
        const iconY = CENTER_Y + iconRadius * Math.sin(toRad(midDeg));

        return {
            path,
            iconX,
            iconY,
            option,
            mainBloc: getBlockByNodeType(option.mainBloc),
        };
    });
});

// --- Core Logic Functions ---
const handleOptionClick = (option: WheelSlot) => {
    if (!option.mainBloc) return;

    graphEvents.emit('node-create', {
        variant: option.mainBloc,
        fromNodeId: props.nodeId,
        options: option.options,
    });

    emit('update:isHovering', false);
};

const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Control' || e.key === 'Meta') {
        isCtrlPressed.value = true;
    }
};
const handleKeyUp = (e: KeyboardEvent) => {
    if (e.key === 'Control' || e.key === 'Meta') {
        isCtrlPressed.value = false;
    }
};

// --- Lifecycle Hooks ---
onMounted(async () => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('keyup', handleKeyUp);
});
</script>

<template>
    <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 scale-75 origin-top -translate-y-4"
        enter-to-class="opacity-100 scale-100 origin-top translate-y-0"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 scale-100 origin-top translate-y-0"
        leave-to-class="opacity-0 scale-75 origin-top -translate-y-4"
    >
        <div v-if="isMenuVisible" class="absolute top-0 left-1/2 z-10 -translate-x-1/2 pt-4">
            <div class="relative drop-shadow-2xl">
                <svg
                    :width="VIEWBOX_WIDTH"
                    :height="VIEWBOX_HEIGHT"
                    :viewBox="`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`"
                    class="overflow-visible"
                    style="filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.3))"
                >
                    <g>
                        <path
                            v-for="(sector, index) in sectors"
                            :key="sector.option.name"
                            :d="sector.path"
                            class="cursor-pointer transition-all duration-200 ease-out"
                            :class="[
                                hoveredIndex === index
                                    ? 'brightness-110'
                                    : 'fill-obsidian/95 stroke-stone-gray/10 hover:brightness-100',
                            ]"
                            :style="{
                                fill: hoveredIndex === index ? sector.mainBloc?.color : undefined,
                            }"
                            stroke-width="1"
                            @mouseenter="hoveredIndex = index"
                            @mouseleave="hoveredIndex = null"
                            @click="handleOptionClick(sector.option)"
                        />
                    </g>
                </svg>

                <!-- Icons Layer -->
                <div class="pointer-events-none absolute inset-0">
                    <div
                        v-for="(sector, index) in sectors"
                        :key="`icon-${sector.option.name}`"
                        class="absolute flex flex-col items-center justify-center gap-1
                            transition-all duration-200"
                        :style="{
                            left: `${sector.iconX}px`,
                            top: `${sector.iconY}px`,
                            transform: `translate(-50%, -50%) ${hoveredIndex === index ? 'scale(1.1)' : 'scale(1)'}`,
                        }"
                    >
                        <UiIcon
                            v-if="sector.mainBloc?.icon"
                            :name="sector.mainBloc.icon"
                            class="h-6 w-6 transition-colors duration-200"
                            :style="{
                                color: hoveredIndex === index ? '#fff' : sector.mainBloc?.color,
                            }"
                        />
                        <!-- Sub-option indicators (dots) -->
                        <div v-if="sector.option.options.length > 0" class="flex gap-0.5">
                            <div
                                v-for="subOpt in sector.option.options"
                                :key="subOpt"
                                class="h-1.5 w-1.5 rounded-full shadow-sm"
                                :style="{
                                    backgroundColor:
                                        hoveredIndex === index
                                            ? '#fff'
                                            : getBlockByNodeType(subOpt)?.color,
                                }"
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </Transition>
</template>

<style scoped></style>
