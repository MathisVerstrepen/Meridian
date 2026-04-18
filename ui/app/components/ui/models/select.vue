<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { RecycleScroller } from 'vue-virtual-scroller';

import {
    MODEL_DROPDOWN_ALL_SECTION_ID,
    MODEL_DROPDOWN_PINNED_SECTION_ID,
    SUBSCRIPTION_PROVIDER_META,
    normalizeModelDropdownSectionOrder,
    parseSubscriptionSectionId,
    type SubscriptionInferenceProvider,
} from '@/constants/modelDropdownSections';
import { SavingStatus } from '@/types/enums';
import type { ModelInfo } from '@/types/model';

type VirtualizedModelRow = {
    id: string;
    model: ModelInfo;
    size: number;
    headerMeta?: string;
    headerTitle?: string;
    headerTooltip?: string;
    warningLabel?: string;
    sectionId: string;
};

type SubscriptionSectionButton = {
    id: string;
    icon: string;
    label: string;
    count: number;
};

// --- Stores ---
const modelStore = useModelStore();
const canvasSaveStore = useCanvasSaveStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { filteredModels: models, isReady } = storeToRefs(modelStore);
const { modelsSettings, modelsDropdownSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;

const {
    connectedSubscriptionProviders,
    hasLoaded: hasLoadedProviderStatuses,
    isProviderConnected,
    refreshInferenceProviderStatuses,
} = useInferenceProviderStatuses();

// --- Props ---
const props = defineProps<{
    model: string;
    setModel: (model: string) => void;
    variant: 'green' | 'grey' | 'terracotta';
    disabled: boolean;
    to: 'right' | 'left';
    from: 'top' | 'bottom';
    preventTriggerOnMount?: boolean;
    pinExactoModels?: boolean;
    onlyImageModels?: boolean;
    hideTool?: boolean;
    requireStructuredOutputs?: boolean;
    requireMeridianTools?: boolean;
    requiredToolNames?: string[];
    excludedProviders?: string[];
}>();

// --- Local State ---
const selected = ref<ModelInfo | undefined>();
const query = ref<string>('');
const buttonRef = ref<HTMLElement | null>(null);
const scrollerRef = ref<{ scrollToItem: (index: number) => void } | null>(null);
const menuPosition = ref({ top: 0, left: 0, zoom: 1 });
const activeJumpSection = ref<string | null>(null);

const TELEPORTED_MENU_WIDTH = 640;
const TELEPORTED_MENU_OFFSET = 4;
const TELEPORTED_MENU_TOP_OFFSET = 276;
const MODEL_ROW_HEIGHT = 40;
const MODEL_ROW_WITH_HEADER_HEIGHT = 70;

let transformPaneObserver: MutationObserver | null = null;
let buttonResizeObserver: ResizeObserver | null = null;

const compatibilityOptions = computed(() => ({
    outputModality: (props.onlyImageModels ? 'image' : 'text') as 'image' | 'text',
    requireStructuredOutputs: props.requireStructuredOutputs,
    requireMeridianTools: props.requireMeridianTools,
    requiredToolNames: props.requiredToolNames,
    excludedProviders: props.excludedProviders,
}));

const meteredHeaderMeta = computed(
    () => `Input · Output · Context${props.hideTool ? '' : ' · Tools'}`,
);
const subscriptionHeaderMeta = computed(() => `Plan · Context${props.hideTool ? '' : ' · Tools'}`);
const normalizedSectionOrder = computed(() =>
    normalizeModelDropdownSectionOrder(modelsDropdownSettings.value.sectionOrder),
);
const pinnedModelIds = computed(() => modelsDropdownSettings.value.pinnedModels ?? []);
const normalizedQuery = computed(() => query.value.trim().toLowerCase());

// --- Computed Properties ---
const compatibleModels = computed(() =>
    modelStore.filterCompatibleModels(models.value, compatibilityOptions.value),
);

const visibleCompatibleModels = computed(() =>
    compatibleModels.value.filter(
        (model) => model.billingType !== 'subscription' || isProviderConnected(model.provider),
    ),
);

const displayCompatibleModels = computed(() =>
    modelStore.filterCompatibleModels(models.value, {
        ...compatibilityOptions.value,
        requireStructuredOutputs: false,
    }),
);

const visibleDisplayModels = computed(() =>
    displayCompatibleModels.value.filter(
        (model) => model.billingType !== 'subscription' || isProviderConnected(model.provider),
    ),
);

const filteredCompatibleModels = computed(() => {
    if (!normalizedQuery.value) {
        return visibleDisplayModels.value;
    }

    return visibleDisplayModels.value.filter((model) =>
        model.name.toLowerCase().includes(normalizedQuery.value),
    );
});

const getModelWarningLabel = (model: ModelInfo) => {
    if (props.requireStructuredOutputs && !model.supportsStructuredOutputs) {
        return 'No native JSON output';
    }

    return undefined;
};

const filteredMeteredModels = computed(() =>
    filteredCompatibleModels.value.filter((model) => model.billingType !== 'subscription'),
);

const filteredSubscriptionModels = computed(() =>
    filteredCompatibleModels.value.filter((model) => model.billingType === 'subscription'),
);

const pinnedMeteredModels = computed(() => {
    if (!isReady.value) {
        return [];
    }

    return pinnedModelIds.value
        .map((id) => filteredMeteredModels.value.find((model) => model.id === id))
        .filter(Boolean);
});

const exactoModels = computed(() => {
    if (!props.pinExactoModels) {
        return [];
    }

    return filteredMeteredModels.value.filter(
        (model) =>
            !pinnedModelIds.value.includes(model.id) &&
            model.name.toLowerCase().includes('(exacto)'),
    );
});

const allModels = computed(() =>
    filteredMeteredModels.value.filter(
        (model) =>
            !pinnedModelIds.value.includes(model.id) &&
            (!props.pinExactoModels || !model.name.toLowerCase().includes('(exacto)')),
    ),
);

const subscriptionModelsByProvider = computed(() => {
    const groups = new Map<SubscriptionInferenceProvider, ModelInfo[]>();

    for (const provider of connectedSubscriptionProviders.value) {
        groups.set(provider, []);
    }

    for (const model of filteredSubscriptionModels.value) {
        const provider = model.provider as SubscriptionInferenceProvider;
        if (!groups.has(provider)) {
            continue;
        }

        groups.get(provider)?.push(model);
    }

    for (const provider of groups.keys()) {
        const providerModels = groups.get(provider) ?? [];
        const pinnedModels = pinnedModelIds.value
            .map((id) => providerModels.find((model) => model.id === id))
            .filter(Boolean);
        const unpinnedModels = providerModels.filter(
            (model) => !pinnedModelIds.value.includes(model.id),
        );
        groups.set(provider, [...pinnedModels, ...unpinnedModels]);
    }

    return groups;
});

const rowData = computed(() => {
    const rows: VirtualizedModelRow[] = [];
    const sectionStartIndices: Record<string, number> = {};
    const subscriptionSections: SubscriptionSectionButton[] = [];

    const appendRows = (
        sectionId: string,
        modelsForSection: ModelInfo[],
        options: {
            headerMeta: string;
            headerTitle: string;
            headerTooltip?: string;
            includeJumpButton?: boolean;
            icon?: string;
        },
    ) => {
        if (!modelsForSection.length) {
            return;
        }

        sectionStartIndices[sectionId] = rows.length;

        if (options.includeJumpButton && options.icon) {
            subscriptionSections.push({
                id: sectionId,
                icon: options.icon,
                label: options.headerTitle,
                count: modelsForSection.length,
            });
        }

        for (const [index, model] of modelsForSection.entries()) {
            rows.push({
                id: `${sectionId}:${model.id}`,
                model,
                size: index === 0 ? MODEL_ROW_WITH_HEADER_HEIGHT : MODEL_ROW_HEIGHT,
                headerTitle: index === 0 ? options.headerTitle : undefined,
                headerMeta: index === 0 ? options.headerMeta : undefined,
                headerTooltip: index === 0 ? options.headerTooltip : undefined,
                warningLabel: getModelWarningLabel(model),
                sectionId,
            });
        }
    };

    for (const sectionId of normalizedSectionOrder.value) {
        if (sectionId === MODEL_DROPDOWN_PINNED_SECTION_ID) {
            appendRows(sectionId, pinnedMeteredModels.value, {
                headerTitle: 'Pinned',
                headerMeta: meteredHeaderMeta.value,
            });
            continue;
        }

        if (sectionId === MODEL_DROPDOWN_ALL_SECTION_ID) {
            appendRows('exacto', exactoModels.value, {
                headerTitle: 'Exacto',
                headerMeta: meteredHeaderMeta.value,
                headerTooltip: 'Exacto Models provide higher tool calling accuracy.',
            });
            appendRows(sectionId, allModels.value, {
                headerTitle: 'All Models',
                headerMeta: meteredHeaderMeta.value,
            });
            continue;
        }

        const provider = parseSubscriptionSectionId(sectionId);
        if (!provider) {
            continue;
        }

        appendRows(sectionId, subscriptionModelsByProvider.value.get(provider) ?? [], {
            headerTitle: SUBSCRIPTION_PROVIDER_META[provider].label,
            headerMeta: subscriptionHeaderMeta.value,
            includeJumpButton: true,
            icon: SUBSCRIPTION_PROVIDER_META[provider].icon,
        });
    }

    return {
        rows,
        sectionStartIndices,
        subscriptionSections,
    };
});

const virtualizedMergedModels = computed(() => rowData.value.rows);
const subscriptionSectionButtons = computed(() => rowData.value.subscriptionSections);

// --- Methods ---
const getTransformationPaneZoom = () => {
    const transformationPane = buttonRef.value?.closest('.vue-flow__transformationpane');

    if (!(transformationPane instanceof HTMLElement)) {
        return 1;
    }

    const transform = window.getComputedStyle(transformationPane).transform;

    if (!transform || transform === 'none') {
        return 1;
    }

    try {
        const matrix = new DOMMatrixReadOnly(transform);
        return Math.hypot(matrix.a, matrix.b) || 1;
    } catch {
        return 1;
    }
};

const updatePanelPosition = () => {
    if (!buttonRef.value) {
        return;
    }

    const rect = buttonRef.value.getBoundingClientRect();
    const zoom = getTransformationPaneZoom();
    const scaledMenuWidth = TELEPORTED_MENU_WIDTH * zoom;

    menuPosition.value = {
        top:
            props.from === 'top'
                ? rect.top - TELEPORTED_MENU_TOP_OFFSET * zoom
                : rect.bottom + TELEPORTED_MENU_OFFSET * zoom,
        left: props.to === 'right' ? rect.right - scaledMenuWidth : rect.left,
        zoom,
    };
};

const clearPositionTracking = () => {
    transformPaneObserver?.disconnect();
    transformPaneObserver = null;

    buttonResizeObserver?.disconnect();
    buttonResizeObserver = null;

    window.removeEventListener('resize', updatePanelPosition);
    window.removeEventListener('scroll', updatePanelPosition, true);
};

const startPositionTracking = async () => {
    clearPositionTracking();
    await nextTick();
    updatePanelPosition();

    const transformationPane = buttonRef.value?.closest('.vue-flow__transformationpane');

    if (transformationPane instanceof HTMLElement) {
        transformPaneObserver = new MutationObserver(updatePanelPosition);
        transformPaneObserver.observe(transformationPane, {
            attributes: true,
            attributeFilter: ['style'],
        });
    }

    if (buttonRef.value) {
        buttonResizeObserver = new ResizeObserver(updatePanelPosition);
        buttonResizeObserver.observe(buttonRef.value);
    }

    window.addEventListener('resize', updatePanelPosition);
    window.addEventListener('scroll', updatePanelPosition, true);
};

const resetQueryAndTracking = () => {
    query.value = '';
    activeJumpSection.value = null;
    clearPositionTracking();
};

const handleTriggerClick = (event: MouseEvent) => {
    startPositionTracking();

    if (props.disabled) {
        return;
    }

    const triggerEl = buttonRef.value;
    if (!triggerEl) {
        return;
    }

    const target = event.target as HTMLElement | null;
    const chevronButton = triggerEl.querySelector('button');
    if (!chevronButton || !target) {
        return;
    }

    if (chevronButton.contains(target)) {
        return;
    }

    const isOpen = chevronButton.getAttribute('aria-expanded') === 'true';
    const input = triggerEl.querySelector('input');

    if (input && input.contains(target)) {
        if (!isOpen) {
            chevronButton.click();
        }
        return;
    }

    chevronButton.click();
};

const jumpToSubscriptionSection = (sectionId: string) => {
    const targetIndex = rowData.value.sectionStartIndices[sectionId];

    if (targetIndex === undefined) {
        return;
    }

    activeJumpSection.value = sectionId;
    scrollerRef.value?.scrollToItem(targetIndex);
};

function initializeSelectedModel() {
    const initialModel =
        visibleDisplayModels.value.find((model) => model.id === props.model) ||
        visibleCompatibleModels.value.find(
            (model) => model.id === modelsSettings.value.defaultModel,
        ) ||
        visibleDisplayModels.value.find(
            (model) => model.id === modelsSettings.value.defaultModel,
        ) ||
        visibleCompatibleModels.value[0] ||
        visibleDisplayModels.value[0];

    if (!initialModel) {
        return;
    }

    selected.value = initialModel;
    if (!props.preventTriggerOnMount) {
        props.setModel(initialModel.id);
    }
}

// --- Watchers ---
watchEffect(() => {
    if (!isReady.value) {
        return;
    }

    const targetModelId = props.model || modelsSettings.value.defaultModel;
    selected.value =
        visibleDisplayModels.value.find((model) => model.id === targetModelId) ||
        visibleCompatibleModels.value.find(
            (model) => model.id === modelsSettings.value.defaultModel,
        ) ||
        visibleDisplayModels.value.find(
            (model) => model.id === modelsSettings.value.defaultModel,
        ) ||
        visibleCompatibleModels.value[0] ||
        visibleDisplayModels.value[0];
});

watch(selected, (newSelected) => {
    if (!newSelected) {
        return;
    }

    if (props.model !== newSelected.id) {
        props.setModel(newSelected.id);
    }

    setNeedSave(SavingStatus.NOT_SAVED);
});

// --- Lifecycle Hooks ---
onMounted(() => {
    if (!hasLoadedProviderStatuses.value) {
        refreshInferenceProviderStatuses().catch((error) => {
            console.error('Failed to load inference provider statuses:', error);
        });
    }

    if (!isReady.value) {
        const unsubscribe = modelStore.$subscribe(() => {
            if (isReady.value) {
                unsubscribe();
                initializeSelectedModel();
            }
        });
    } else {
        initializeSelectedModel();
    }
});

onUnmounted(() => {
    clearPositionTracking();
});
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative">
            <!-- Trigger -->
            <div
                ref="buttonRef"
                class="ui-models-trigger group/trigger relative h-full w-full cursor-default
                    overflow-hidden rounded-2xl border-2 text-left transition-all
                    focus:outline-none"
                :class="{
                    [`bg-soft-silk/15 border-olive-grove-dark dark:text-olive-grove-dark
                    text-anthracite`]: variant === 'green',
                    'bg-obsidian/20 dark:border-stone-gray/20 border-soft-silk/20 text-soft-silk/80':
                        variant === 'grey',
                    [`dark:bg-soft-silk/50 border-terracotta-clay-dark
                    dark:text-terracotta-clay-dark text-anthracite bg-[#612411]/50`]:
                        variant === 'terracotta',
                    'cursor-not-allowed opacity-50': disabled,
                    'cursor-pointer': !disabled,
                }"
                @click="handleTriggerClick"
            >
                <div class="flex items-center">
                    <span v-if="selected?.icon" class="ml-3 flex shrink-0 items-center">
                        <UiIcon :name="'models/' + selected.icon" class="h-4 w-4" />
                    </span>

                    <HeadlessComboboxInput
                        class="relative w-full border-none pr-10 pl-2 text-sm leading-5 font-bold
                            tracking-tight focus:ring-0 focus:outline-none"
                        :display-value="(model: unknown) => (model as ModelInfo).name"
                        :class="{
                            'py-1': variant === 'green' || variant === 'terracotta',
                            'py-2': variant === 'grey',
                            'cursor-not-allowed': disabled,
                        }"
                        @change="query = $event.target.value"
                    />
                </div>
                <HeadlessComboboxButton
                    v-if="!disabled"
                    class="absolute inset-y-0 right-0 flex cursor-pointer items-center pr-1.5"
                >
                    <UiIcon
                        name="FlowbiteChevronDownOutline"
                        class="h-6 w-6 transition-transform duration-300
                            group-focus-within/trigger:rotate-180"
                    />
                </HeadlessComboboxButton>
            </div>

            <!-- Dropdown -->
            <HeadlessTransitionRoot
                enter="transition ease-out duration-150"
                enter-from="opacity-0 -translate-y-1"
                enter-to="opacity-100 translate-y-0"
                leave="transition ease-in duration-100"
                leave-from="opacity-100"
                leave-to="opacity-0"
                @after-leave="resetQueryAndTracking"
            >
                <Teleport to="body">
                    <HeadlessComboboxOptions
                        v-if="!disabled"
                        static
                        class="ui-models-panel fixed z-40 h-fit w-160 overflow-hidden rounded-2xl
                            border text-base focus:outline-none"
                        :style="{
                            top: `${menuPosition.top}px`,
                            left: `${menuPosition.left}px`,
                            transform: `scale(${menuPosition.zoom})`,
                            transformOrigin: 'top left',
                        }"
                    >
                        <!-- Subscription quick-jump pills -->
                        <div
                            v-if="subscriptionSectionButtons.length"
                            class="border-stone-gray/10 flex flex-wrap items-center gap-1.5 border-b
                                px-3 py-2.5"
                        >
                            <span
                                class="text-stone-gray/50 mr-1 text-[9px] font-bold tracking-[0.2em]
                                    uppercase"
                            >
                                Jump
                            </span>
                            <button
                                v-for="section in subscriptionSectionButtons"
                                :key="section.id"
                                type="button"
                                class="group/pill border-stone-gray/10 text-soft-silk/80
                                    hover:border-ember-glow/40 hover:text-soft-silk
                                    hover:bg-ember-glow/5 inline-flex shrink-0 items-center gap-1.5
                                    rounded-lg border px-2.5 py-1 text-xs font-semibold
                                    transition-all duration-150"
                                :class="{
                                    [`border-ember-glow/50 bg-ember-glow/10 text-soft-silk
                                    shadow-[0_0_0_1px_rgba(235,94,40,0.15)]`]:
                                        activeJumpSection === section.id,
                                    'bg-anthracite/40': activeJumpSection !== section.id,
                                }"
                                @click.stop="jumpToSubscriptionSection(section.id)"
                            >
                                <UiIcon :name="section.icon" class="h-3.5 w-3.5" />
                                <span>{{ section.label }}</span>
                                <span
                                    class="bg-stone-gray/10 text-stone-gray/80
                                        group-hover/pill:bg-ember-glow/15
                                        group-hover/pill:text-ember-glow rounded px-1 text-[10px]
                                        font-bold tabular-nums transition-colors"
                                >
                                    {{ section.count }}
                                </span>
                            </button>
                        </div>

                        <!-- List -->
                        <RecycleScroller
                            v-if="virtualizedMergedModels.length"
                            ref="scrollerRef"
                            :items="virtualizedMergedModels"
                            :item-size="null"
                            :min-item-size="MODEL_ROW_HEIGHT"
                            key-field="id"
                            class="nowheel custom_scroll max-h-64 px-1.5 py-1"
                        >
                            <template #default="{ item: modelRow }">
                                <HeadlessComboboxOption
                                    v-slot="{ selected: isSelected, active: isActive }"
                                    :value="modelRow.model"
                                    as="template"
                                >
                                    <UiModelsSelectItem
                                        :model="modelRow.model"
                                        :active="isActive"
                                        :selected="isSelected"
                                        :header-title="modelRow.headerTitle"
                                        :header-meta="modelRow.headerMeta"
                                        :header-tooltip="modelRow.headerTooltip"
                                        :hide-tool="hideTool"
                                        :warning-label="modelRow.warningLabel"
                                    />
                                </HeadlessComboboxOption>
                            </template>
                        </RecycleScroller>

                        <!-- Empty state -->
                        <div
                            v-else
                            class="relative flex flex-col items-center justify-center gap-3 px-6
                                py-10 text-center select-none"
                        >
                            <div
                                class="border-stone-gray/15 bg-anthracite/50 relative flex h-12 w-12
                                    items-center justify-center rounded-2xl border"
                            >
                                <UiIcon name="MdiMagnify" class="text-stone-gray/40 h-6 w-6" />
                                <span
                                    aria-hidden="true"
                                    class="bg-ember-glow/60 absolute -top-1 -right-1 h-2 w-2
                                        rounded-full"
                                />
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <p class="text-soft-silk/90 text-sm font-semibold">
                                    No models match that query
                                </p>
                                <p class="text-stone-gray/60 text-xs">
                                    Try a different keyword or clear the search.
                                </p>
                            </div>
                        </div>

                        <!-- Footer: keyboard hints -->
                        <div
                            class="border-stone-gray/10 text-stone-gray/60 flex items-center
                                justify-between gap-3 border-t px-4 py-2 text-[10px]"
                        >
                            <div class="flex items-center gap-3">
                                <span class="flex items-center gap-1.5">
                                    <kbd
                                        class="border-stone-gray/20 bg-anthracite/60
                                            text-soft-silk/80 inline-flex items-center
                                            justify-center rounded border px-1.5 py-0.5 pt-1
                                            font-mono text-[9px] leading-none font-bold"
                                        >↑↓</kbd
                                    >
                                    <span class="tracking-wide uppercase">navigate</span>
                                </span>
                                <span class="flex items-center gap-1.5">
                                    <kbd
                                        class="border-stone-gray/20 bg-anthracite/60
                                            text-soft-silk/80 inline-flex items-center
                                            justify-center rounded border px-1.5 py-0.5 pt-1
                                            font-mono text-[9px] leading-none font-bold"
                                        >↵</kbd
                                    >
                                    <span class="tracking-wide uppercase">select</span>
                                </span>
                                <span class="flex items-center gap-1.5">
                                    <kbd
                                        class="border-stone-gray/20 bg-anthracite/60
                                            text-soft-silk/80 inline-flex items-center
                                            justify-center rounded border px-1.5 py-0.5 pt-1
                                            font-mono text-[9px] leading-none font-bold"
                                        >ESC</kbd
                                    >
                                    <span class="tracking-wide uppercase">close</span>
                                </span>
                            </div>
                        </div>
                    </HeadlessComboboxOptions>
                </Teleport>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped>
.ui-models-trigger {
    font-variant-numeric: tabular-nums;
}

.ui-models-panel {
    background:
        radial-gradient(
            120% 80% at 0% 0%,
            color-mix(in oklab, var(--color-ember-glow) 7%, transparent) 0%,
            transparent 55%
        ),
        linear-gradient(
            180deg,
            color-mix(in oklab, var(--color-obsidian) 85%, transparent) 0%,
            color-mix(in oklab, var(--color-obsidian) 75%, transparent) 100%
        );
    border-color: color-mix(in oklab, var(--color-stone-gray) 18%, transparent);
    box-shadow:
        0 1px 0 0 color-mix(in oklab, var(--color-soft-silk) 6%, transparent) inset,
        0 0 0 1px color-mix(in oklab, var(--color-obsidian) 60%, transparent),
        0 30px 60px -20px rgba(0, 0, 0, 0.55),
        0 10px 20px -10px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    font-variant-numeric: tabular-nums;
}

.ui-models-panel::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image: radial-gradient(
        circle at 1px 1px,
        color-mix(in oklab, var(--color-soft-silk) 4%, transparent) 1px,
        transparent 0
    );
    background-size: 14px 14px;
    mix-blend-mode: overlay;
    opacity: 0.35;
}
</style>
