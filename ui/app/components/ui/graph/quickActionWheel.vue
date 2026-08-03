<script setup lang="ts">
import type { GraphQuickAction } from '@/composables/useGraphQuickActions';

const props = defineProps<{
    actions: readonly GraphQuickAction[];
    x: number;
    y: number;
}>();

const emit = defineEmits<{
    activate: [action: GraphQuickAction];
    close: [];
}>();

const WHEEL_CLEARANCE = 208;
const EXTERNAL_WHEEL_CLEARANCE = 304;
const ROOT_SIZE = 408;
const ROOT_INNER_RADIUS = 66;
const ROOT_OUTER_RADIUS = 184;
const ROOT_LABEL_RADIUS = 124;
const ARC_SIZE = 640;
const ARC_OUTER_RADIUS = 286;
const ARC_SEAM_OVERLAP = 2;
const ARC_INNER_RADIUS = ROOT_OUTER_RADIUS - ARC_SEAM_OVERLAP;
const ARC_VISIBLE_THICKNESS = ARC_OUTER_RADIUS - ROOT_OUTER_RADIUS;
const ARC_LABEL_RADIUS = ROOT_OUTER_RADIUS + ARC_VISIBLE_THICKNESS * 0.56;
const ARC_LEAVE_DELAY = 140;
const menu = ref<HTMLElement | null>(null);
const currentActions = ref<readonly GraphQuickAction[]>(props.actions);
const parentLevels = ref<Array<readonly GraphQuickAction[]>>([]);
const externalParent = ref<GraphQuickAction | null>(null);
const externalOpenMode = ref<'pointer' | 'keyboard' | null>(null);
const activeIndex = ref(0);
let arcLeaveTimer: ReturnType<typeof setTimeout> | null = null;

const hasExternalFan = computed(() =>
    props.actions.some((action) => action.childrenDisplay === 'external-fan' && action.children?.length),
);
const externalActions = computed(() => externalParent.value?.children ?? []);
const externalParentIndex = computed(() =>
    currentActions.value.findIndex((action) => action.id === externalParent.value?.id),
);

const clampedPosition = computed(() => {
    const clearance = hasExternalFan.value ? EXTERNAL_WHEEL_CLEARANCE : WHEEL_CLEARANCE;
    const maxX = Math.max(clearance, window.innerWidth - clearance);
    const maxY = Math.max(clearance, window.innerHeight - clearance);
    return {
        x: Math.min(Math.max(props.x, clearance), maxX),
        y: Math.min(Math.max(props.y, clearance), maxY),
    };
});

const actionAngle = (index: number, count: number) =>
    -Math.PI / 2 + (index * Math.PI * 2) / count;

const rootSegmentGeometry = (index: number) => {
    const count = currentActions.value.length;
    const segmentSize = (Math.PI * 2) / count;
    const middle = actionAngle(index, count);
    return {
        start: middle - segmentSize / 2 + 0.003,
        end: middle + segmentSize / 2 - 0.003,
        middle,
    };
};

const externalArcGeometry = (index: number) => {
    const count = externalActions.value.length;
    const parentAngle = actionAngle(externalParentIndex.value, currentActions.value.length);
    const span = Math.min(Math.PI * 0.9, Math.max(Math.PI * 0.42, count * 0.38));
    const segmentSize = span / count;
    const start = parentAngle - span / 2 + index * segmentSize + 0.003;
    const end = start + segmentSize - 0.006;
    return { start, end, middle: (start + end) / 2 };
};

const annularPoint = (size: number, angle: number, radius: number) => ({
    x: size / 2 + Math.cos(angle) * radius,
    y: size / 2 + Math.sin(angle) * radius,
});

const annularSegmentPath = (
    size: number,
    innerRadius: number,
    outerRadius: number,
    start: number,
    end: number,
) => {
    const outerStart = annularPoint(size, start, outerRadius);
    const outerEnd = annularPoint(size, end, outerRadius);
    const innerEnd = annularPoint(size, end, innerRadius);
    const innerStart = annularPoint(size, start, innerRadius);
    const largeArc = end - start > Math.PI ? 1 : 0;
    return [
        `M ${outerStart.x} ${outerStart.y}`,
        `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
        `L ${innerEnd.x} ${innerEnd.y}`,
        `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
        'Z',
    ].join(' ');
};

const segmentStyle = (size: number, clipId: string) => {
    return {
        width: `${size}px`,
        height: `${size}px`,
        clipPath: `url(#${clipId})`,
        transform: 'translate(-50%, -50%)',
    };
};

const rootClipId = (index: number) => `quick-action-root-segment-${index}`;
const externalClipId = (index: number) => `quick-action-external-segment-${index}`;

const rootSegmentPath = (index: number) => {
    const { start, end } = rootSegmentGeometry(index);
    return annularSegmentPath(ROOT_SIZE, ROOT_INNER_RADIUS, ROOT_OUTER_RADIUS, start, end);
};

const externalSegmentPath = (index: number) => {
    const { start, end } = externalArcGeometry(index);
    return annularSegmentPath(ARC_SIZE, ARC_INNER_RADIUS, ARC_OUTER_RADIUS, start, end);
};

const itemStyle = (index: number) => {
    return segmentStyle(ROOT_SIZE, rootClipId(index));
};

const rootLabelStyle = (index: number) => {
    const { middle } = rootSegmentGeometry(index);
    return {
        left: `${ROOT_SIZE / 2 + Math.cos(middle) * ROOT_LABEL_RADIUS}px`,
        top: `${ROOT_SIZE / 2 + Math.sin(middle) * ROOT_LABEL_RADIUS}px`,
    };
};

const externalItemStyle = (index: number, action: GraphQuickAction) => {
    return {
        ...segmentStyle(ARC_SIZE, externalClipId(index)),
        '--quick-action-accent': action.accentColor ?? 'var(--color-stone-gray)',
    };
};

const externalFanOutlinePath = computed(() => {
    if (!externalActions.value.length) return '';
    const first = externalArcGeometry(0);
    const last = externalArcGeometry(externalActions.value.length - 1);
    return annularSegmentPath(
        ARC_SIZE,
        ARC_INNER_RADIUS,
        ARC_OUTER_RADIUS,
        first.start,
        last.end,
    );
});

const externalLabelStyle = (index: number) => {
    const { middle } = externalArcGeometry(index);
    return {
        left: `${ARC_SIZE / 2 + Math.cos(middle) * ARC_LABEL_RADIUS}px`,
        top: `${ARC_SIZE / 2 + Math.sin(middle) * ARC_LABEL_RADIUS}px`,
    };
};

const compactHandleColor = (action: GraphQuickAction) => {
    if (action.compactHandle?.category === 'prompt') return 'var(--color-node-cat-prompt)';
    if (action.compactHandle?.category === 'context') return 'var(--color-node-cat-context)';
    return 'var(--color-node-cat-attachment)';
};

const compactHandleArrowClass = (action: GraphQuickAction) => {
    if (action.compactHandle?.category === 'attachment') {
        return action.compactHandle.direction === 'target' ? '-rotate-90' : 'rotate-90';
    }
    return action.compactHandle?.direction === 'source' ? 'rotate-180' : '';
};

const actionButtons = () =>
    Array.from(menu.value?.querySelectorAll<HTMLButtonElement>('[data-quick-action]') ?? []);

const focusAt = (index: number) => {
    const buttons = actionButtons();
    if (!buttons.length) return;
    activeIndex.value = (index + buttons.length) % buttons.length;
    nextTick(() => actionButtons()[activeIndex.value]?.focus());
};

const enterSubmenu = (action: GraphQuickAction) => {
    if (!action.children?.length) return;
    if (arcLeaveTimer) clearTimeout(arcLeaveTimer);
    externalParent.value = null;
    externalOpenMode.value = null;
    parentLevels.value.push(currentActions.value);
    currentActions.value = action.children;
    focusAt(0);
};

const isExternalParent = (action: GraphQuickAction) =>
    !parentLevels.value.length &&
    action.childrenDisplay === 'external-fan' && !!action.children?.length;

const cancelArcClose = () => {
    if (arcLeaveTimer) clearTimeout(arcLeaveTimer);
    arcLeaveTimer = null;
};

const showExternalChildren = (action: GraphQuickAction, mode: 'pointer' | 'keyboard') => {
    if (!isExternalParent(action)) return;
    cancelArcClose();
    externalParent.value = action;
    externalOpenMode.value = mode;
};

const schedulePointerArcClose = () => {
    if (externalOpenMode.value !== 'pointer') return;
    cancelArcClose();
    arcLeaveTimer = setTimeout(() => {
        if (externalOpenMode.value === 'pointer') {
            externalParent.value = null;
            externalOpenMode.value = null;
        }
        arcLeaveTimer = null;
    }, ARC_LEAVE_DELAY);
};

const hideExternalChildren = () => {
    cancelArcClose();
    externalParent.value = null;
    externalOpenMode.value = null;
};

const closeExternalChildren = () => {
    const parentIndex = externalParentIndex.value;
    hideExternalChildren();
    if (parentIndex >= 0) focusAt(parentIndex);
};

const onRootFocus = (action: GraphQuickAction, index: number) => {
    activeIndex.value = index;
    if (externalParent.value && action.id !== externalParent.value.id) hideExternalChildren();
};

const goBack = () => {
    const parent = parentLevels.value.pop();
    if (!parent) return;
    currentActions.value = parent;
    focusAt(0);
};

const activate = (action: GraphQuickAction) => {
    if (action.children?.length) {
        if (isExternalParent(action)) {
            showExternalChildren(action, 'keyboard');
            nextTick(() => focusAt(currentActions.value.length));
            return;
        }
        enterSubmenu(action);
        return;
    }
    emit('activate', action);
};

const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
        event.preventDefault();
        emit('close');
    } else if (event.key === 'Backspace' && externalParent.value) {
        event.preventDefault();
        closeExternalChildren();
    } else if (event.key === 'Backspace' && parentLevels.value.length) {
        event.preventDefault();
        goBack();
    } else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        event.preventDefault();
        focusAt(activeIndex.value + 1);
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        event.preventDefault();
        focusAt(activeIndex.value - 1);
    } else if (event.key === 'Home') {
        event.preventDefault();
        focusAt(0);
    } else if (event.key === 'End') {
        event.preventDefault();
        focusAt(actionButtons().length - 1);
    }
};

const onOutsidePointerDown = (event: PointerEvent) => {
    if (!(event.target instanceof Node) || !menu.value?.contains(event.target)) emit('close');
};
const onResize = () => emit('close');

onMounted(() => {
    window.addEventListener('pointerdown', onOutsidePointerDown, true);
    window.addEventListener('resize', onResize);
    focusAt(0);
});

onUnmounted(() => {
    cancelArcClose();
    window.removeEventListener('pointerdown', onOutsidePointerDown, true);
    window.removeEventListener('resize', onResize);
});
</script>

<template>
    <Teleport to="body">
        <div
            ref="menu"
            role="menu"
            aria-label="Canvas quick actions"
            data-testid="quick-action-wheel"
            :data-wheel-outer-radius="hasExternalFan ? ARC_OUTER_RADIUS : ROOT_OUTER_RADIUS"
            :data-main-outer-radius="ROOT_OUTER_RADIUS"
            :data-outer-inner-radius="ARC_INNER_RADIUS"
            :data-outer-label-radius="ARC_LABEL_RADIUS"
            class="fixed z-50 h-0 w-0 outline-none"
            :style="{ left: `${clampedPosition.x}px`, top: `${clampedPosition.y}px` }"
            @keydown="onKeyDown"
        >
            <svg class="absolute h-0 w-0" aria-hidden="true">
                <defs>
                    <clipPath
                        v-for="(_action, index) in currentActions"
                        :id="rootClipId(index)"
                        :key="rootClipId(index)"
                        clipPathUnits="userSpaceOnUse"
                    >
                        <path :d="rootSegmentPath(index)" />
                    </clipPath>
                    <clipPath
                        v-for="(_action, index) in externalActions"
                        :id="externalClipId(index)"
                        :key="externalClipId(index)"
                        clipPathUnits="userSpaceOnUse"
                    >
                        <path :d="externalSegmentPath(index)" />
                    </clipPath>
                </defs>
            </svg>

            <svg
                data-testid="quick-action-root-rim"
                :width="ROOT_SIZE"
                :height="ROOT_SIZE"
                :viewBox="`0 0 ${ROOT_SIZE} ${ROOT_SIZE}`"
                class="text-soft-silk/15 pointer-events-none absolute top-1/2 left-1/2 z-10 -translate-x-1/2 -translate-y-1/2
                    overflow-visible drop-shadow-[0_14px_24px_rgba(0,0,0,0.34)]"
                aria-hidden="true"
            >
                <circle
                    :cx="ROOT_SIZE / 2"
                    :cy="ROOT_SIZE / 2"
                    :r="ROOT_OUTER_RADIUS"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1"
                />
                <circle
                    :cx="ROOT_SIZE / 2"
                    :cy="ROOT_SIZE / 2"
                    :r="ROOT_INNER_RADIUS"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1"
                />
            </svg>

            <svg
                v-if="externalParent"
                data-testid="quick-action-external-rim"
                :width="ARC_SIZE"
                :height="ARC_SIZE"
                :viewBox="`0 0 ${ARC_SIZE} ${ARC_SIZE}`"
                class="text-soft-silk/15 pointer-events-none absolute top-1/2 left-1/2 z-0 -translate-x-1/2 -translate-y-1/2
                    overflow-visible drop-shadow-[0_10px_18px_rgba(0,0,0,0.28)]"
                aria-hidden="true"
            >
                <path
                    :d="externalFanOutlinePath"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1"
                />
            </svg>

            <button
                v-if="parentLevels.length"
                type="button"
                aria-label="Back to previous quick actions"
                class="bg-anthracite/70 border-soft-silk/15 text-soft-silk absolute top-1/2 left-1/2 z-20 flex h-14 w-14
                    -translate-x-1/2 -translate-y-1/2 cursor-pointer flex-col items-center justify-center rounded-full border
                    text-[11px] shadow-lg backdrop-blur-xl backdrop-saturate-150 motion-safe:transition-colors hover:bg-stone-gray/80
                    focus-visible:bg-slate-blue/80 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none
                    motion-reduce:transition-none"
                @click="goBack"
            >
                <UiIcon name="MaterialSymbolsArrowBackRounded" class="h-5 w-5" />
                Back
            </button>

            <button
                v-for="(action, index) in currentActions"
                :key="action.id"
                type="button"
                role="menuitem"
                data-quick-action
                data-root-quick-action-segment
                data-wheel-layer="root"
                data-wheel-glass-surface
                :data-action-id="action.id"
                :data-danger-action="action.danger || undefined"
                :tabindex="index === activeIndex ? 0 : -1"
                :aria-label="action.label"
                :aria-expanded="isExternalParent(action) ? externalParent?.id === action.id : undefined"
                :style="itemStyle(index)"
                class="bg-anthracite/68 text-soft-silk absolute top-1/2 left-1/2 z-10 cursor-pointer backdrop-blur-xl
                    backdrop-saturate-150 motion-safe:transition-colors hover:bg-stone-gray/78 focus-visible:bg-slate-blue/80
                    focus-visible:outline-none motion-reduce:transition-none"
                :class="{
                    'bg-terracotta-clay/22 text-terracotta-clay hover:bg-terracotta-clay/32 focus-visible:bg-terracotta-clay/38':
                        action.danger,
                    'cursor-not-allowed opacity-70': action.locked,
                    'bg-slate-blue/65': externalParent?.id === action.id,
                }"
                @focus="onRootFocus(action, index)"
                @pointerenter="isExternalParent(action) && showExternalChildren(action, 'pointer')"
                @pointerleave="isExternalParent(action) && schedulePointerArcClose()"
                @click="activate(action)"
            >
                <span
                    data-root-action-label
                    class="absolute flex w-18 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-0.5 text-center
                        text-[11px] leading-tight font-semibold tracking-tight"
                    :style="rootLabelStyle(index)"
                >
                    <UiIcon :name="action.icon" class="h-5 w-5 shrink-0" />
                    <span class="line-clamp-2">{{ action.label }}</span>
                    <UiIcon
                        v-if="action.children?.length"
                        name="FlowbiteChevronDownOutline"
                        class="h-4 w-4 shrink-0"
                    />
                    <UiIcon
                        v-else-if="action.locked"
                        name="MaterialSymbolsLockOutline"
                        class="h-4 w-4 shrink-0"
                    />
                </span>
            </button>

            <button
                v-for="(action, index) in externalActions"
                :key="`external-${action.id}`"
                type="button"
                role="menuitem"
                data-quick-action
                data-external-quick-action
                data-wheel-layer="outer"
                data-wheel-glass-surface
                :data-action-id="action.id"
                :data-compact-handle="action.compactHandle ? '' : undefined"
                :tabindex="currentActions.length + index === activeIndex ? 0 : -1"
                :aria-label="action.label"
                :title="action.compactHandle ? action.label : undefined"
                :style="externalItemStyle(index, action)"
                class="quick-action-colored-segment bg-anthracite/64 text-soft-silk absolute top-1/2 left-1/2 z-0 cursor-pointer
                    backdrop-blur-xl backdrop-saturate-150 motion-safe:transition-colors focus-visible:outline-none
                    motion-reduce:transition-none"
                :class="{ 'cursor-not-allowed opacity-70': action.locked }"
                @focus="activeIndex = currentActions.length + index"
                @pointerenter="cancelArcClose"
                @pointerleave="schedulePointerArcClose"
                @click="emit('activate', action)"
            >
                <span
                    v-if="action.compactHandle"
                    data-external-action-label
                    data-compact-workflow-label
                    class="absolute -translate-x-1/2 -translate-y-1/2"
                    :style="externalLabelStyle(index)"
                >
                    <span class="relative block">
                        <UiIcon :name="action.icon" class="h-6 w-6 shrink-0" />
                        <span
                            data-workflow-handle-indicator
                            :data-handle-category="action.compactHandle.category"
                            :data-handle-direction="action.compactHandle.direction"
                            class="border-anthracite absolute -right-2 -bottom-1 flex h-3.5 w-3.5 items-center justify-center rounded-full
                                border shadow-sm"
                            :style="{ backgroundColor: compactHandleColor(action) }"
                        >
                            <UiIcon
                                name="MdiArrowUp"
                                class="text-anthracite h-2.5 w-2.5"
                                :class="compactHandleArrowClass(action)"
                            />
                        </span>
                    </span>
                </span>
                <span
                    v-else
                    data-external-action-label
                    class="absolute flex w-18 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-0.5 text-center
                        text-[11px] leading-tight font-semibold tracking-tight"
                    :style="externalLabelStyle(index)"
                >
                    <UiIcon :name="action.icon" class="h-5 w-5 shrink-0" />
                    <span class="line-clamp-2">{{ action.label }}</span>
                    <UiIcon
                        v-if="action.locked"
                        name="MaterialSymbolsLockOutline"
                        class="h-4 w-4 shrink-0"
                    />
                </span>
            </button>
        </div>
    </Teleport>
</template>

<style scoped>
.quick-action-colored-segment {
    background: color-mix(
        in oklab,
        var(--quick-action-accent) 18%,
        color-mix(in srgb, var(--color-anthracite) 64%, transparent)
    );
}

.quick-action-colored-segment:hover {
    background: color-mix(
        in oklab,
        var(--quick-action-accent) 30%,
        color-mix(in srgb, var(--color-anthracite) 68%, transparent)
    );
}

.quick-action-colored-segment:focus-visible {
    background: color-mix(
        in oklab,
        var(--quick-action-accent) 40%,
        color-mix(in srgb, var(--color-anthracite) 64%, transparent)
    );
}
</style>
