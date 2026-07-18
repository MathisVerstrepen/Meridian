<script lang="ts" setup>
import type { WheelSlot } from '@/types/settings';
import { NodeCategoryEnum } from '@/types/enums';
import { calculateWheelSectorGeometry } from '@/utils/graphGeometry';
import type { QuickWorkflowDirection } from '@/utils/quickWorkflow';
import { isValidQuickWorkflowSlot } from '@/utils/quickWorkflow';

const emit = defineEmits<{
    'update:isHovering': [value: boolean];
}>();

const props = withDefaults(
    defineProps<{
        nodeId: string;
        options?: WheelSlot[];
        isHovering: boolean;
        category: NodeCategoryEnum;
        direction: QuickWorkflowDirection;
        actionable?: boolean;
        anchorOffset?: string;
    }>(),
    {
        options: () => [],
        actionable: true,
        anchorOffset: '50%',
    },
);

const isCtrlPressed = ref(false);
const hoveredIndex = ref<number | null>(null);
const graphEvents = useGraphEvents();
const { getBlockByNodeType } = useBlocks();

const RADIUS = 120;
const INNER_RADIUS = 40;
const VIEWBOX_WIDTH = 260;
const VIEWBOX_HEIGHT = 125;
const CENTER_X = VIEWBOX_WIDTH / 2;
const CENTER_Y = 0;

const filteredOptions = computed(() =>
    props.options.filter((option) =>
        isValidQuickWorkflowSlot(option, props.category, props.direction),
    ),
);
const isMenuVisible = computed(
    () =>
        props.actionable &&
        props.isHovering &&
        isCtrlPressed.value &&
        filteredOptions.value.length > 0,
);
const rotation = computed(() => {
    if (props.category === NodeCategoryEnum.ATTACHMENT) {
        return props.direction === 'source' ? -90 : 90;
    }
    return props.direction === 'target' ? 180 : 0;
});
const anchorStyle = computed(() => ({
    left: props.category === NodeCategoryEnum.ATTACHMENT ? '0' : props.anchorOffset,
    top: props.category === NodeCategoryEnum.ATTACHMENT ? '50%' : '0',
}));
const wheelStyle = computed(() => ({
    transform: `translateX(-50%) rotate(${rotation.value}deg)`,
    transformOrigin: '50% 0',
}));

const sectors = computed(() => {
    const geometry = calculateWheelSectorGeometry(filteredOptions.value.length, {
        radius: RADIUS,
        innerRadius: INNER_RADIUS,
        centerX: CENTER_X,
        centerY: CENTER_Y,
    });

    return geometry.map((sector, index) => {
        const option = filteredOptions.value[index]!;
        return {
            ...sector,
            option,
            mainBloc: option.mainBloc ? getBlockByNodeType(option.mainBloc) : undefined,
        };
    });
});

const handleOptionClick = (slot: WheelSlot) => {
    if (!props.actionable || !isValidQuickWorkflowSlot(slot, props.category, props.direction)) return;
    graphEvents.emit('node-create', {
        fromNodeId: props.nodeId,
        category: props.category,
        direction: props.direction,
        slot,
    });
    emit('update:isHovering', false);
};
const setModifierState = (event: KeyboardEvent, pressed: boolean) => {
    if (event.key === 'Control' || event.key === 'Meta') isCtrlPressed.value = pressed;
};
const handleKeyDown = (event: KeyboardEvent) => setModifierState(event, true);
const handleKeyUp = (event: KeyboardEvent) => setModifierState(event, false);
const clearModifierState = () => (isCtrlPressed.value = false);

onMounted(() => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', clearModifierState);
});
onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('keyup', handleKeyUp);
    window.removeEventListener('blur', clearModifierState);
});
</script>

<template>
    <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 scale-75"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-75"
    >
        <div
            v-if="isMenuVisible"
            class="pointer-events-none absolute z-40"
            :style="{ ...anchorStyle, transformOrigin: '0 0' }"
            data-wheel-transition-root
            :data-wheel-side="
                category === NodeCategoryEnum.ATTACHMENT
                    ? direction === 'source'
                        ? 'right'
                        : 'left'
                    : direction === 'source'
                      ? 'bottom'
                      : 'top'
            "
            :data-wheel-rotation="rotation"
        >
            <div class="relative drop-shadow-2xl" :style="wheelStyle">
                <svg
                    data-wheel-root-svg
                    :width="VIEWBOX_WIDTH"
                    :height="VIEWBOX_HEIGHT"
                    :viewBox="`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`"
                    class="pointer-events-none overflow-visible"
                >
                    <path
                        :d="`M ${CENTER_X} ${CENTER_Y} L ${CENTER_X + INNER_RADIUS} ${CENTER_Y} A ${INNER_RADIUS} ${INNER_RADIUS} 0 0 1 ${CENTER_X - INNER_RADIUS} ${CENTER_Y} Z`"
                        class="pointer-events-auto fill-transparent"
                        data-wheel-hover-bridge
                        @mouseenter="emit('update:isHovering', true)"
                    />
                    <path
                        v-for="(sector, index) in sectors"
                        :key="sector.option.name"
                        :d="sector.path"
                        class="fill-obsidian/95 stroke-stone-gray/10 pointer-events-auto cursor-pointer transition-all duration-200 ease-out"
                        :class="{ 'brightness-110': hoveredIndex === index }"
                        :style="{ fill: hoveredIndex === index ? sector.mainBloc?.color : undefined }"
                        stroke-width="1"
                        :data-wheel-slot="sector.option.name"
                        @mouseenter="
                            hoveredIndex = index;
                            emit('update:isHovering', true);
                        "
                        @mouseleave="hoveredIndex = null"
                        @click="handleOptionClick(sector.option)"
                    />
                </svg>
                <div class="pointer-events-none absolute inset-0">
                    <div
                        v-for="(sector, index) in sectors"
                        :key="`icon-${sector.option.name}`"
                        class="absolute flex flex-col items-center justify-center gap-1 transition-all duration-200"
                        :style="{
                            left: `${sector.iconX}px`,
                            top: `${sector.iconY}px`,
                            transform: `translate(-50%, -50%) rotate(${-rotation}deg) ${hoveredIndex === index ? 'scale(1.1)' : 'scale(1)'}`,
                        }"
                        data-wheel-content-upright="true"
                    >
                        <UiIcon
                            v-if="sector.mainBloc?.icon"
                            :name="sector.mainBloc.icon"
                            class="h-6 w-6 transition-colors duration-200"
                            :style="{
                                color:
                                    hoveredIndex === index
                                        ? '#fff'
                                        : sector.mainBloc.icon === 'MdiGithub'
                                          ? 'var(--color-soft-silk)'
                                          : sector.mainBloc.color,
                            }"
                            :data-github-icon-contrast="
                                sector.mainBloc.icon === 'MdiGithub' ? 'wheel' : undefined
                            "
                        />
                        <div v-if="sector.option.options.length > 0" class="flex gap-0.5">
                            <div
                                v-for="subOption in sector.option.options"
                                :key="subOption"
                                class="h-1.5 w-1.5 rounded-full shadow-sm"
                                :style="{
                                    backgroundColor:
                                        hoveredIndex === index
                                            ? '#fff'
                                            : getBlockByNodeType(subOption)?.color,
                                }"
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </Transition>
</template>
