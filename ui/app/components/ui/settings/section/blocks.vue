<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { NodeCategoryEnum } from '@/types/enums';
import type { WheelSlot } from '@/types/settings';
import type { QuickWorkflowDirection } from '@/utils/quickWorkflow';
import { getQuickWorkflowConfig, isValidQuickWorkflowSlot } from '@/utils/quickWorkflow';

interface WheelDescriptor {
    category: NodeCategoryEnum;
    categoryLabel: string;
    direction: QuickWorkflowDirection;
    directionLabel: 'Input' | 'Output';
}

const globalSettingsStore = useSettingsStore();
const { blockSettings } = storeToRefs(globalSettingsStore);
const contextWheelEntry = SETTINGS_ENTRY.blocksContextWheel;
const tablist = ref<HTMLElement>();
const activeIndex = ref(1);
const liveMessage = ref('Context output selected. Creates after the current node.');

const wheels: WheelDescriptor[] = [
    { category: NodeCategoryEnum.CONTEXT, categoryLabel: 'Context', direction: 'target', directionLabel: 'Input' },
    { category: NodeCategoryEnum.CONTEXT, categoryLabel: 'Context', direction: 'source', directionLabel: 'Output' },
    { category: NodeCategoryEnum.PROMPT, categoryLabel: 'Prompt', direction: 'target', directionLabel: 'Input' },
    { category: NodeCategoryEnum.PROMPT, categoryLabel: 'Prompt', direction: 'source', directionLabel: 'Output' },
    { category: NodeCategoryEnum.ATTACHMENT, categoryLabel: 'Attachment', direction: 'target', directionLabel: 'Input' },
    { category: NodeCategoryEnum.ATTACHMENT, categoryLabel: 'Attachment', direction: 'source', directionLabel: 'Output' },
];

const activeWheel = computed(() => wheels[activeIndex.value]!);
const activeConfig = computed(() => getQuickWorkflowConfig(activeWheel.value.category, activeWheel.value.direction));
const activeSlots = computed(() => blockSettings.value[activeConfig.value.settingsKey]);
const activeId = computed(() => wheelId(activeWheel.value));

function wheelId(wheel: WheelDescriptor) {
    return `quick-workflow-${wheel.category}-${wheel.direction}`;
}

function directionMeaning(wheel: WheelDescriptor) {
    return wheel.direction === 'target' ? 'before the current node' : 'after the current node';
}

function categoryColor(category: NodeCategoryEnum) {
    if (category === NodeCategoryEnum.CONTEXT) return 'var(--color-node-cat-context)';
    if (category === NodeCategoryEnum.PROMPT) return 'var(--color-node-cat-prompt)';
    return 'var(--color-node-cat-attachment)';
}

function visibleSlots(wheel: WheelDescriptor): WheelSlot[] {
    const config = getQuickWorkflowConfig(wheel.category, wheel.direction);
    return Array.from({ length: 4 }, (_, index) =>
        blockSettings.value[config.settingsKey][index] ?? {
            name: `Slot ${index + 1}`,
            mainBloc: null,
            options: [],
        },
    );
}

function counts(wheel: WheelDescriptor) {
    const slots = visibleSlots(wheel);
    const configured = slots.filter((slot) => slot.mainBloc !== null || slot.options.length > 0);
    return {
        configured: configured.length,
        invalid: configured.filter(
            (slot) => !isValidQuickWorkflowSlot(slot, wheel.category, wheel.direction),
        ).length,
    };
}

function activateWheel(index: number, shouldFocus = false) {
    activeIndex.value = index;
    const wheel = wheels[index]!;
    liveMessage.value = `${wheel.categoryLabel} ${wheel.directionLabel.toLowerCase()} selected. Creates ${directionMeaning(wheel)}.`;
    if (shouldFocus) {
        nextTick(() => tablist.value?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[index]?.focus());
    }
}

function onMatrixKeydown(event: KeyboardEvent) {
    const row = Math.floor(activeIndex.value / 2);
    const column = activeIndex.value % 2;
    let next = activeIndex.value;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') next = row * 2 + (column === 0 ? 1 : 0);
    else if (event.key === 'ArrowUp') next = ((row + 2) % 3) * 2 + column;
    else if (event.key === 'ArrowDown') next = ((row + 1) % 3) * 2 + column;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 5;
    else return;
    event.preventDefault();
    activateWheel(next, true);
}

function replaceSlot(payload: { index: number; slot: WheelSlot }) {
    const key = activeConfig.value.settingsKey;
    const replacement = blockSettings.value[key].map((slot) => ({
        name: slot.name,
        mainBloc: slot.mainBloc,
        options: [...slot.options],
    }));
    while (replacement.length <= payload.index) {
        replacement.push({ name: `Slot ${replacement.length + 1}`, mainBloc: null, options: [] });
    }
    replacement[payload.index] = {
        name: payload.slot.name,
        mainBloc: payload.slot.mainBloc,
        options: [...payload.slot.options],
    };
    blockSettings.value[key] = replacement;
}
</script>

<template>
    <div class="quick-workflow-workbench min-w-0 py-6" data-testid="quick-workflow-workbench">
        <p class="text-stone-gray/80 max-w-3xl text-sm leading-relaxed">
            {{ contextWheelEntry.description }}
        </p>

        <div class="workbench-grid mt-6 grid min-w-0 grid-cols-1 gap-0">
            <section class="wheel-selector border-stone-gray/10 min-w-0 border-b pb-6" aria-label="Wheel selector">
                <div class="text-stone-gray mb-2 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] px-3 text-xs font-semibold uppercase">
                    <span>Input · before</span>
                    <span>Output · after</span>
                </div>
                <div
                    ref="tablist"
                    role="tablist"
                    aria-label="Quick workflow wheels"
                    class="grid min-w-0 grid-cols-2"
                    @keydown="onMatrixKeydown"
                >
                    <button
                        v-for="(wheel, index) in wheels"
                        :id="`${wheelId(wheel)}-tab`"
                        :key="wheelId(wheel)"
                        type="button"
                        role="tab"
                        :aria-selected="activeIndex === index"
                        aria-controls="quick-workflow-active-panel"
                        :tabindex="activeIndex === index ? 0 : -1"
                        :aria-label="`${wheel.categoryLabel} ${wheel.directionLabel}, creates ${directionMeaning(wheel)}, ${counts(wheel).configured} configured, ${counts(wheel).invalid} need repair`"
                        class="wheel-tab quick-workflow-control border-stone-gray/10 text-soft-silk hover:bg-stone-gray/8
                            focus-visible:ring-ember-glow relative min-w-0 bg-transparent p-3 text-left transition-colors
                            focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-inset focus-visible:outline-none"
                        :class="{ 'bg-ember-glow/10': activeIndex === index }"
                        @click="activateWheel(index)"
                    >
                        <span class="flex min-w-0 items-center gap-2 text-sm font-semibold">
                            <span
                                aria-hidden="true"
                                data-wheel-category-marker
                                class="h-2.5 w-4 shrink-0 rounded-full"
                                :style="{ backgroundColor: categoryColor(wheel.category) }"
                            />
                            <span class="min-w-0 break-words">{{ wheel.categoryLabel }} {{ wheel.directionLabel }}</span>
                        </span>
                        <span class="text-stone-gray mt-2 block text-xs">
                            {{ counts(wheel).configured }} configured
                        </span>
                        <span v-if="counts(wheel).invalid" class="text-ember-glow mt-1 block text-xs font-semibold">
                            {{ counts(wheel).invalid }} need repair
                        </span>
                        <span v-else class="text-stone-gray mt-1 block text-xs">0 need repair</span>
                        <span
                            v-if="activeIndex === index"
                            aria-hidden="true"
                            data-wheel-selected-rail
                            class="absolute inset-y-2 left-0 w-1"
                            :style="{ backgroundColor: categoryColor(wheel.category) }"
                        />
                    </button>
                </div>
            </section>

            <section
                id="quick-workflow-active-panel"
                role="tabpanel"
                :aria-labelledby="`${activeId}-tab`"
                class="active-wheel-panel min-w-0 pt-6"
            >
                <header class="border-stone-gray/10 min-w-0 border-b pb-4">
                    <h4 class="text-soft-silk mt-1 break-words text-lg font-semibold">
                        {{ activeWheel.categoryLabel }} {{ activeWheel.directionLabel.toLowerCase() }}
                    </h4>
                    <p class="text-stone-gray mt-1 text-sm">
                        Creates {{ directionMeaning(activeWheel) }} · {{ counts(activeWheel).configured }} configured ·
                        {{ counts(activeWheel).invalid }} need repair
                    </p>
                    <div
                        class="text-soft-silk mt-2 flex min-w-0 flex-wrap items-center gap-2 text-sm"
                        :aria-label="
                            activeWheel.direction === 'target'
                                ? 'Input flow: Preset creates before Current node'
                                : 'Output flow: Current node creates before Preset'
                        "
                    >
                        <template v-if="activeWheel.direction === 'target'">
                            <span aria-hidden="true">[Preset]</span>
                            <span aria-hidden="true">→</span>
                            <span aria-hidden="true">Current node</span>
                        </template>
                        <template v-else>
                            <span aria-hidden="true">Current node</span>
                            <span aria-hidden="true">→</span>
                            <span aria-hidden="true">[Preset]</span>
                        </template>
                    </div>
                </header>

                <UiSettingsSectionWheelCreator
                    class="mt-4"
                    :slots="activeSlots"
                    :category="activeWheel.category"
                    :direction="activeWheel.direction"
                    :label="`${activeWheel.categoryLabel} ${activeWheel.directionLabel}`"
                    :id-context="activeId"
                    @replace-slot="replaceSlot"
                />
            </section>
        </div>
        <p class="sr-only" aria-live="polite" aria-atomic="true">{{ liveMessage }}</p>
    </div>
</template>

<style scoped>
.quick-workflow-workbench {
    container: quick-workflow / inline-size;
}

@container quick-workflow (min-width: 30rem) {
    :deep(.slot-tabs) {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    :deep(.choice-grid) {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@container quick-workflow (min-width: 47.5rem) {
    .workbench-grid {
        grid-template-columns: minmax(15rem, 0.72fr) minmax(0, 1.28fr);
        align-items: start;
    }

    .wheel-selector {
        border-right-width: 1px;
        border-bottom-width: 0;
        padding-right: 1.5rem;
        padding-bottom: 0;
    }

    .active-wheel-panel {
        padding-top: 0;
        padding-left: 1.5rem;
    }
}

.wheel-tab:nth-child(even) {
    border-left-width: 1px;
}

.wheel-tab:nth-child(n + 3) {
    border-top-width: 1px;
}

@media (prefers-reduced-motion: reduce) {
    :deep(.quick-workflow-control) {
        transition-duration: 0s !important;
        transform: none !important;
    }
}
</style>
