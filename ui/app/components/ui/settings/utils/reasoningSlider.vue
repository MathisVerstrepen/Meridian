<script lang="ts" setup>
import { REASONING_EFFORTS } from '@/types/enums';
import type { ReasoningEffortEnum } from '@/types/enums';
import {
    isReasoningEffortSupported,
    REASONING_EFFORT_LABELS,
} from '@/utils/reasoningEffort';

defineOptions({
    inheritAttrs: false,
});

const props = defineProps<{
    id?: string;
    currentReasoningEffort: ReasoningEffortEnum;
    reasoningEfforts?: number;
}>();

const emits = defineEmits<{
    (event: 'update:reasoningEffort', value: ReasoningEffortEnum): void;
}>();

const sliderRef = ref<HTMLElement | null>(null);
const geometryRef = ref<HTMLElement | null>(null);
const isDragging = ref(false);
// Keep REASONING_EFFORTS in its canonical mask/bit order; the control presents it low-to-high.
const displayedEfforts: readonly ReasoningEffortEnum[] = [...REASONING_EFFORTS].reverse();
const effortCount = displayedEfforts.length;

function markerPositionPercent(index: number) {
    return ((index + 0.5) / effortCount) * 100;
}

const currentDisplayIndex = computed(() => Math.max(
    0,
    displayedEfforts.indexOf(props.currentReasoningEffort),
));
const currentEffortIsSupported = computed(() => isReasoningEffortSupported(
    props.currentReasoningEffort,
    props.reasoningEfforts,
));
const hasSupportedEffort = computed(() => REASONING_EFFORTS.some((effort) => isSupported(effort)));
const currentLabel = computed(() => REASONING_EFFORT_LABELS[props.currentReasoningEffort]);
const currentValueText = computed(() => currentEffortIsSupported.value
    ? currentLabel.value
    : `${currentLabel.value} (unavailable for this model)`);
const markerPosition = computed(() => `${markerPositionPercent(currentDisplayIndex.value)}%`);
const trackInset = `${markerPositionPercent(0)}%`;
const activeTrackWidth = computed(
    () => `${(currentDisplayIndex.value / (effortCount - 1)) * 100}%`,
);

function isSupported(effort: ReasoningEffortEnum) {
    return isReasoningEffortSupported(effort, props.reasoningEfforts);
}

function selectEffort(effort: ReasoningEffortEnum) {
    if (isSupported(effort)) {
        emits('update:reasoningEffort', effort);
    }
}

function nearestSupportedEffort(rawIndex: number) {
    let nearest: ReasoningEffortEnum | null = null;
    let nearestDistance = Number.POSITIVE_INFINITY;

    for (const [index, effort] of displayedEfforts.entries()) {
        if (!isSupported(effort)) continue;

        const distance = Math.abs(index - rawIndex);
        if (distance < nearestDistance) {
            nearest = effort;
            nearestDistance = distance;
        }
    }

    return nearest;
}

function selectFromPointer(event: PointerEvent) {
    const geometry = geometryRef.value;
    if (!geometry || !hasSupportedEffort.value) return;

    const rect = geometry.getBoundingClientRect();
    if (rect.width === 0) return;

    const rawIndex = Math.min(
        effortCount - 1,
        Math.max(0, (((event.clientX - rect.left) / rect.width) * effortCount) - 0.5),
    );
    const effort = nearestSupportedEffort(rawIndex);

    if (effort) selectEffort(effort);
}

function onPointerDown(event: PointerEvent) {
    const slider = sliderRef.value;
    if (!slider || !hasSupportedEffort.value) return;

    const marker = event.target instanceof HTMLElement
        ? event.target.closest<HTMLElement>('[data-reasoning-effort]')
        : null;
    if (marker?.getAttribute('aria-disabled') === 'true') return;

    isDragging.value = true;
    slider.focus({ preventScroll: true });
    try {
        slider.setPointerCapture(event.pointerId);
    } catch {
        // Synthetic pointer events do not always have an active pointer to capture.
    }
    event.preventDefault();
    selectFromPointer(event);
}

function onPointerMove(event: PointerEvent) {
    if (!isDragging.value) return;
    event.preventDefault();
    selectFromPointer(event);
}

function onPointerEnd(event: PointerEvent) {
    if (!isDragging.value) return;

    selectFromPointer(event);
    isDragging.value = false;
    const slider = sliderRef.value;
    if (slider?.hasPointerCapture(event.pointerId)) {
        slider.releasePointerCapture(event.pointerId);
    }
}

function selectInDirection(direction: 1 | -1) {
    const start = currentDisplayIndex.value + direction;
    for (
        let index = start;
        index >= 0 && index < displayedEfforts.length;
        index += direction
    ) {
        const effort = displayedEfforts[index];
        if (effort && isSupported(effort)) {
            selectEffort(effort);
            return;
        }
    }
}

function onKeydown(event: KeyboardEvent) {
    if (['ArrowRight', 'ArrowUp', 'ArrowLeft', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
    } else {
        return;
    }

    if (!hasSupportedEffort.value) return;

    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') {
        selectInDirection(1);
        return;
    }
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') {
        selectInDirection(-1);
        return;
    }

    const efforts = event.key === 'Home' ? displayedEfforts : [...displayedEfforts].reverse();
    const effort = efforts.find((candidate) => isSupported(candidate));
    if (effort) selectEffort(effort);
}
</script>

<template>
    <div v-bind="$attrs" class="min-w-0 w-full">
        <div class="mb-2 flex min-w-0 items-center justify-between gap-3">
            <span class="text-stone-gray text-[10px] font-semibold tracking-[0.16em] uppercase">
                Reasoning effort
            </span>
            <span
                data-testid="reasoning-effort-current"
                class="truncate text-right text-xs font-semibold"
                :class="currentEffortIsSupported ? 'text-soft-silk' : 'text-stone-gray'"
            >
                {{ currentLabel }}
                <span v-if="!currentEffortIsSupported" class="font-normal">unavailable</span>
            </span>
        </div>

        <div
            :id="id"
            ref="sliderRef"
            data-testid="reasoning-effort-slider"
            role="slider"
            tabindex="0"
            aria-label="Reasoning effort"
            :aria-disabled="!hasSupportedEffort"
            :aria-valuemin="0"
            :aria-valuemax="displayedEfforts.length - 1"
            :aria-valuenow="currentDisplayIndex"
            :aria-valuetext="currentValueText"
            class="border-stone-gray/20 bg-obsidian/60 focus-visible:ring-ember-glow/60 relative min-w-0
                cursor-grab rounded-xl border px-1.5 pt-3 pb-1 outline-none select-none
                focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-obsidian
                active:cursor-grabbing"
            :class="{
                'cursor-not-allowed': !hasSupportedEffort,
                'touch-none': isDragging,
            }"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerEnd"
            @pointercancel="onPointerEnd"
            @keydown="onKeydown"
        >
            <div
                ref="geometryRef"
                data-testid="reasoning-effort-geometry"
                class="relative min-w-0"
            >
                <div
                    data-testid="reasoning-effort-track"
                    class="bg-stone-gray/25 absolute top-[3px] z-0 h-1 overflow-hidden rounded-full"
                    :style="{ left: trackInset, right: trackInset }"
                    aria-hidden="true"
                >
                    <span
                        data-testid="reasoning-effort-active-track"
                        class="absolute inset-y-0 left-0 rounded-full transition-[width,background-color]
                            duration-200 motion-reduce:transition-none"
                        :class="currentEffortIsSupported ? 'bg-ember-glow shadow-[0_0_12px_rgba(235,94,40,0.45)]' : 'bg-stone-gray/45'"
                        :style="{ width: activeTrackWidth }"
                        aria-hidden="true"
                    />
                </div>

                <span
                    data-testid="reasoning-effort-thumb"
                    class="border-obsidian pointer-events-none absolute -top-[3px] z-20 h-4 w-4 -translate-x-1/2 rounded-full border-2
                        transition-[left,background-color,box-shadow] duration-200 motion-reduce:transition-none"
                    :class="currentEffortIsSupported
                        ? 'bg-ember-glow shadow-[0_0_16px_rgba(235,94,40,0.65)]'
                        : 'bg-stone-gray shadow-none'"
                    :style="{ left: markerPosition }"
                    aria-hidden="true"
                />

                <div class="relative z-10 grid grid-cols-7">
                    <div
                        v-for="effort in displayedEfforts"
                        :key="effort"
                        :data-testid="`reasoning-effort-marker-${effort}`"
                        :data-reasoning-effort="effort"
                        :data-selected="currentReasoningEffort === effort"
                        :aria-disabled="!isSupported(effort)"
                        class="flex min-w-0 cursor-pointer flex-col items-center gap-1 text-center"
                        :class="!isSupported(effort) ? 'cursor-not-allowed' : ''"
                    >
                        <span
                            class="relative z-10 h-2.5 w-2.5 rounded-full border transition-[background-color,border-color,transform]
                                duration-200 motion-reduce:transition-none"
                            :class="[
                                !isSupported(effort)
                                    ? 'border-stone-gray/70 bg-obsidian'
                                    : 'border-stone-gray/60 bg-obsidian',
                                currentReasoningEffort === effort && currentEffortIsSupported
                                    ? 'border-ember-glow bg-ember-glow scale-110'
                                    : '',
                                currentReasoningEffort === effort && !currentEffortIsSupported
                                    ? 'border-stone-gray bg-stone-gray/70'
                                    : '',
                            ]"
                            aria-hidden="true"
                        />
                        <span
                            class="w-full px-px text-[8px] leading-tight font-medium tracking-tight sm:text-[9px]"
                            :class="[
                                !isSupported(effort) ? 'text-stone-gray/60' : 'text-stone-gray',
                                currentReasoningEffort === effort && currentEffortIsSupported
                                    ? 'text-ember-glow'
                                    : '',
                                currentReasoningEffort === effort && !currentEffortIsSupported
                                    ? 'text-stone-gray'
                                    : '',
                            ]"
                        >
                            {{ REASONING_EFFORT_LABELS[effort] }}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
