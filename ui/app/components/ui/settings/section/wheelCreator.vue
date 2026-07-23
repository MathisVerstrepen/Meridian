<script lang="ts" setup>
import type { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { WheelSlot } from '@/types/settings';
import type { QuickWorkflowDirection } from '@/utils/quickWorkflow';
import { getQuickWorkflowConfig, isValidQuickWorkflowSlot } from '@/utils/quickWorkflow';

const props = defineProps<{
    slots: readonly WheelSlot[];
    category: NodeCategoryEnum;
    direction: QuickWorkflowDirection;
    label: string;
    idContext: string;
}>();

const emit = defineEmits<{
    'replace-slot': [payload: { index: number; slot: WheelSlot }];
}>();

const { getBlockByNodeType } = useBlocks();
const activeSlotIndex = ref(0);
const tablist = ref<HTMLElement>();
const detailHeading = ref<HTMLElement>();
const clearButton = ref<HTMLButtonElement>();
const liveMessage = ref('');
const panelId = computed(() => `${props.idContext}-slot-panel`);
const config = computed(() => getQuickWorkflowConfig(props.category, props.direction));
const displayedSlots = computed<WheelSlot[]>(() =>
    Array.from({ length: 4 }, (_, index) =>
        props.slots[index] ?? { name: `Slot ${index + 1}`, mainBloc: null, options: [] },
    ),
);
const activeSlot = computed(() => displayedSlots.value[activeSlotIndex.value]!);
const activeState = computed(() => slotState(activeSlot.value));
const groupPrefix = computed(() => `${props.idContext}-slot-${activeSlotIndex.value + 1}`);
const hasAllowedMain = computed(
    () => activeSlot.value.mainBloc !== null && config.value.allowedMainBlocks.includes(activeSlot.value.mainBloc),
);
const linkedHelper = computed(() =>
    activeSlot.value.mainBloc === null ? 'Select a main block first' : 'Select a valid main block first',
);

function isEmpty(slot: WheelSlot) {
    return slot.mainBloc === null && slot.options.length === 0;
}

function slotState(slot: WheelSlot): 'empty' | 'configured' | 'invalid' {
    if (isEmpty(slot)) return 'empty';
    return isValidQuickWorkflowSlot(slot, props.category, props.direction) ? 'configured' : 'invalid';
}

function blockName(nodeType: NodeTypeEnum | null) {
    return nodeType ? (getBlockByNodeType(nodeType)?.name ?? nodeType) : 'Empty';
}

function blockPresentation(nodeType: NodeTypeEnum | null) {
    return nodeType ? getBlockByNodeType(nodeType) : undefined;
}

function activateSlot(index: number, shouldFocus = false) {
    activeSlotIndex.value = index;
    liveMessage.value = `${displayedSlots.value[index]!.name} selected for editing.`;
    if (shouldFocus) {
        nextTick(() => tablist.value?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[index]?.focus());
    }
}

function onSlotKeydown(event: KeyboardEvent) {
    let next = activeSlotIndex.value;
    if (event.key === 'ArrowLeft') next = (next + 3) % 4;
    else if (event.key === 'ArrowRight') next = (next + 1) % 4;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = 3;
    else return;
    event.preventDefault();
    activateSlot(next, true);
}

function replaceActive(slot: WheelSlot, message: string) {
    emit('replace-slot', {
        index: activeSlotIndex.value,
        slot: { name: slot.name, mainBloc: slot.mainBloc, options: [...slot.options] },
    });
    liveMessage.value = message;
}

function selectMain(mainBloc: NodeTypeEnum, checked: boolean) {
    if (!checked || !config.value.allowedMainBlocks.includes(mainBloc)) return;
    replaceActive(
        { ...activeSlot.value, mainBloc, options: [...activeSlot.value.options] },
        `${activeSlot.value.name} main block changed to ${blockName(mainBloc)}.`,
    );
}

function toggleOption(option: NodeTypeEnum, checked: boolean) {
    if (!hasAllowedMain.value || !config.value.allowedOptions.includes(option)) return;
    const options = checked
        ? activeSlot.value.options.includes(option)
            ? [...activeSlot.value.options]
            : [...activeSlot.value.options, option]
        : activeSlot.value.options.filter((candidate) => candidate !== option);
    replaceActive(
        { ...activeSlot.value, options },
        `${blockName(option)} ${checked ? 'linked to' : 'removed from'} ${activeSlot.value.name}.`,
    );
}

function clearSlot() {
    replaceActive(
        { name: activeSlot.value.name, mainBloc: null, options: [] },
        `${activeSlot.value.name} cleared.`,
    );
    nextTick(() =>
        tablist.value?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[activeSlotIndex.value]?.focus(),
    );
}

function repairSlot() {
    const current = activeSlot.value;
    const mainAllowed = current.mainBloc !== null && config.value.allowedMainBlocks.includes(current.mainBloc);
    const repaired: WheelSlot = mainAllowed
        ? {
              name: current.name,
              mainBloc: current.mainBloc,
              options: current.options.filter((option) => config.value.allowedOptions.includes(option)),
          }
        : { name: current.name, mainBloc: null, options: [] };
    replaceActive(repaired, `${current.name} repaired.`);
    nextTick(() => {
        if (isEmpty(repaired)) detailHeading.value?.focus();
        else clearButton.value?.focus();
    });
}

const invalidDescription = computed(() => {
    if (activeState.value !== 'invalid') return '';
    const slot = activeSlot.value;
    const parts: string[] = [];
    if (!slot.mainBloc || !config.value.allowedMainBlocks.includes(slot.mainBloc)) {
        parts.push(`main block ${blockName(slot.mainBloc)}`);
    }
    const invalidOptions = slot.options.filter((option) => !config.value.allowedOptions.includes(option));
    if (invalidOptions.length) parts.push(`linked ${invalidOptions.map(blockName).join(', ')}`);
    return `${parts.join(' and ')} incompatible. Runtime omits this slot until it is repaired.`;
});
</script>

<template>
    <div class="min-w-0">
        <div
            ref="tablist"
            role="tablist"
            :aria-label="`${label} slots`"
            class="slot-tabs border-stone-gray/15 grid min-w-0 grid-cols-2 border-b"
            @keydown="onSlotKeydown"
        >
            <UiSettingsSectionQuickWorkflowSlotButton
                v-for="(slot, index) in displayedSlots"
                :key="index"
                :slot-data="slot"
                :position="index + 1"
                :selected="activeSlotIndex === index"
                :state="slotState(slot)"
                :tab-index="activeSlotIndex === index ? 0 : -1"
                :tab-id="`${idContext}-slot-tab-${index + 1}`"
                :panel-id="panelId"
                :summary="blockName(slot.mainBloc)"
                :summary-icon="blockPresentation(slot.mainBloc)?.icon"
                :summary-color="blockPresentation(slot.mainBloc)?.color"
                @activate="activateSlot(index)"
            />
        </div>

        <section
            :id="panelId"
            role="tabpanel"
            :aria-labelledby="`${idContext}-slot-tab-${activeSlotIndex + 1}`"
            tabindex="0"
            class="focus-visible:ring-ember-glow mt-4 min-w-0 rounded-none border-0 bg-transparent focus-visible:ring-2
                focus-visible:ring-inset focus-visible:outline-none"
        >
            <div class="flex min-w-0 flex-wrap items-start justify-between gap-3">
                <div class="min-w-0">
                    <h5 ref="detailHeading" tabindex="-1" class="text-soft-silk break-words font-semibold outline-none">
                        Configure {{ activeSlot.name }}
                    </h5>
                    <p class="text-stone-gray mt-1 text-sm">
                        {{ activeState === 'empty' ? 'Empty slot' : activeState === 'invalid' ? 'Needs repair' : 'Configured slot' }}
                    </p>
                </div>
                <div class="flex shrink-0 gap-2">
                    <button
                        v-if="activeState === 'invalid'"
                        type="button"
                        class="quick-workflow-control border-ember-glow text-soft-silk hover:bg-stone-gray/8
                            focus-visible:ring-ember-glow rounded-md border bg-transparent px-3 py-1.5 text-sm font-semibold
                            transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:outline-none"
                        :aria-label="`Repair ${activeSlot.name}`"
                        @click="repairSlot"
                    >
                        Repair
                    </button>
                    <button
                        ref="clearButton"
                        type="button"
                        class="quick-workflow-control border-stone-gray/15 text-soft-silk hover:bg-stone-gray/8
                            focus-visible:ring-ember-glow rounded-md border bg-transparent px-3 py-1.5 text-sm transition-colors
                            focus-visible:ring-2 focus-visible:ring-inset focus-visible:outline-none disabled:cursor-not-allowed
                            disabled:opacity-40"
                        :disabled="activeState === 'empty'"
                        :aria-label="`Clear ${activeSlot.name}`"
                        @click="clearSlot"
                    >
                        Clear
                    </button>
                </div>
            </div>

            <p v-if="invalidDescription" role="status" class="border-ember-glow/60 text-soft-silk mt-4 border-l-2 py-1 pl-3 text-sm">
                {{ invalidDescription }}
            </p>

            <fieldset class="border-stone-gray/10 mt-5 min-w-0 border-t pt-5">
                <legend class="text-soft-silk font-semibold">Main block</legend>
                <p class="text-stone-gray mt-1 text-sm">Choose the primary block created by this slot.</p>
                <div class="choice-grid mt-3 grid min-w-0 grid-cols-1 gap-2">
                    <UiSettingsSectionQuickWorkflowBlockChoice
                        v-for="nodeType in config.allowedMainBlocks"
                        :key="nodeType"
                        :node-type="nodeType"
                        control="radio"
                        :checked="activeSlot.mainBloc === nodeType"
                        :group-name="`${groupPrefix}-main`"
                        @change="selectMain(nodeType, $event)"
                    />
                </div>
            </fieldset>

            <fieldset v-if="config.allowedOptions.length" class="border-stone-gray/10 mt-6 min-w-0 border-t pt-5">
                <legend class="text-soft-silk font-semibold">Linked blocks</legend>
                <p class="text-stone-gray mt-1 text-sm">
                    {{ hasAllowedMain ? 'Choose supporting blocks created with the main block.' : linkedHelper }}
                </p>
                <div class="choice-grid mt-3 grid min-w-0 grid-cols-1 gap-2">
                    <UiSettingsSectionQuickWorkflowBlockChoice
                        v-for="nodeType in config.allowedOptions"
                        :key="nodeType"
                        :node-type="nodeType"
                        control="checkbox"
                        :checked="activeSlot.options.includes(nodeType)"
                        :group-name="`${groupPrefix}-linked`"
                        :disabled="!hasAllowedMain"
                        @change="toggleOption(nodeType, $event)"
                    />
                </div>
            </fieldset>
        </section>
        <p class="sr-only" aria-live="polite" aria-atomic="true">{{ liveMessage }}</p>
    </div>
</template>
