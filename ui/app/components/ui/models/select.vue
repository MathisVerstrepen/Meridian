<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { RecycleScroller } from 'vue-virtual-scroller';
import { SavingStatus } from '@/types/enums';
import type { ModelInfo } from '@/types/model';

// --- Stores ---
const modelStore = useModelStore();
const canvasSaveStore = useCanvasSaveStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { filteredModels: models, isReady } = storeToRefs(modelStore);
const { modelsSettings, modelsDropdownSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;
const { getModel } = modelStore;

// --- Props ---
const props = defineProps<{
    model: string;
    setModel: (model: string) => void;
    variant: 'green' | 'grey' | 'terracotta';
    disabled: boolean;
    to: 'right' | 'left';
    from: 'top' | 'bottom';
    teleport?: boolean;
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
const open = ref(false);
const selected = ref<ModelInfo | undefined>();
const query = ref<string>('');
const buttonRef = ref<HTMLElement | null>(null);
const menuPosition = ref({ top: 0, left: 0 });
const exactoModels = ref<ModelInfo[]>([]);

const nExactoModels = computed(() => exactoModels.value.length);
const compatibilityOptions = computed(() => ({
    outputModality: (props.onlyImageModels ? 'image' : 'text') as 'image' | 'text',
    requireStructuredOutputs: props.requireStructuredOutputs,
    requireMeridianTools: props.requireMeridianTools,
    requiredToolNames: props.requiredToolNames,
    excludedProviders: props.excludedProviders,
}));

// --- Computed Properties ---
const compatibleModels = computed(() =>
    modelStore.filterCompatibleModels(models.value, compatibilityOptions.value),
);

const filteredModels = computed(() => {
    if (!query.value) return compatibleModels.value;

    return compatibleModels.value.filter((model) =>
        model.name.toLowerCase().includes(query.value.toLowerCase()),
    );
});

const pinnedModels = computed(() => {
    if (!isReady.value) return [];
    return (
        modelsDropdownSettings.value.pinnedModels
            .map((id) => compatibleModels.value.find((model) => model.id === id))
            .filter(Boolean)
            .filter((model) => model.name.toLowerCase().includes(query.value.toLowerCase()))
    );
});

const nPinnedModels = computed(() => pinnedModels.value.length);

// The list of pinned models AND all models, both filtered by the search query
const mergedModels = computed(() => {
    if (!isReady.value) {
        return [];
    }

    const unpinned = filteredModels.value.filter(
        (model) =>
            !modelsDropdownSettings.value.pinnedModels.includes(model.id) &&
            exactoModels.value.indexOf(model) === -1,
    );

    return [...pinnedModels.value, ...exactoModels.value, ...unpinned];
});

const nMergedModels = computed(() => mergedModels.value.length);

const getModelRowSize = (index: number) => {
    const hasPinnedHeader = index === 0 && nPinnedModels.value > 0;
    const hasExactoHeader =
        nExactoModels.value > 0 &&
        index === nPinnedModels.value &&
        nMergedModels.value > nPinnedModels.value + nExactoModels.value;
    const hasAllHeader =
        index === nExactoModels.value + nPinnedModels.value &&
        nMergedModels.value > nExactoModels.value + nPinnedModels.value;

    if (hasExactoHeader || hasAllHeader) {
        return 72;
    }

    if (hasPinnedHeader) {
        return 68;
    }

    return 40;
};

const virtualizedMergedModels = computed(() =>
    mergedModels.value.map((model, index) => ({
        id: model.id,
        model,
        size: getModelRowSize(index),
    })),
);

// --- Methods ---
const updatePanelPosition = () => {
    if (buttonRef.value) {
        const rect = buttonRef.value.getBoundingClientRect();
        menuPosition.value = {
            top: rect.top + 40,
            left: rect.left + (props.to === 'right' ? rect.width - 640 : 0),
        };
    }
};

function initializeSelectedModel() {
    const initialModel =
        compatibleModels.value.find((model) => model.id === props.model) ||
        compatibleModels.value.find((model) => model.id === modelsSettings.value.defaultModel) ||
        compatibleModels.value[0];
    if (initialModel) {
        selected.value = initialModel;
        if (!props.preventTriggerOnMount) {
            props.setModel(initialModel.id);
        }
    }
}

// --- Watchers ---
watchEffect(() => {
    if (!isReady.value) {
        return; // Halt execution until the store is ready
    }

    const targetModelId = props.model || modelsSettings.value.defaultModel;
    selected.value =
        compatibleModels.value.find((model) => model.id === targetModelId) ||
        compatibleModels.value.find((model) => model.id === modelsSettings.value.defaultModel) ||
        compatibleModels.value[0] ||
        getModel(modelsSettings.value.defaultModel);
});

watch(selected, (newSelected) => {
    if (!newSelected) return;

    if (props.model !== newSelected.id) {
        props.setModel(newSelected.id);
    }

    setNeedSave(SavingStatus.NOT_SAVED);
});

watch(open, (newVal) => {
    if (newVal) {
        nextTick(updatePanelPosition);
    }
});

watch(
    () => props.pinExactoModels,
    (newVal) => {
        if (newVal) {
            exactoModels.value = compatibleModels.value.filter((model) =>
                model.name.toLowerCase().includes('(exacto)'),
            );
        } else {
            exactoModels.value = [];
        }
    },
    { immediate: true },
);

watch(
    compatibleModels,
    () => {
        if (props.pinExactoModels) {
            exactoModels.value = compatibleModels.value.filter((model) =>
                model.name.toLowerCase().includes('(exacto)'),
            );
        }
    },
    { deep: true },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    // Ensure the model store is ready before proceeding
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
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative">
            <div
                ref="buttonRef"
                class="relative h-full w-full cursor-default overflow-hidden rounded-2xl border-2
                    text-left focus:outline-none"
                :class="{
                    [`bg-soft-silk/15 border-olive-grove-dark dark:text-olive-grove-dark
                    text-anthracite`]: variant === 'green',
                    'bg-obsidian/20 dark:border-stone-gray/20 border-soft-silk/20 text-soft-silk/80':
                        variant === 'grey',
                    [`dark:bg-soft-silk/50 border-terracotta-clay-dark
                    dark:text-terracotta-clay-dark text-anthracite bg-[#612411]/50`]:
                        variant === 'terracotta',
                    'cursor-not-allowed opacity-50': disabled,
                }"
                @click="nextTick(updatePanelPosition)"
            >
                <div class="flex items-center">
                    <span v-if="selected?.icon" class="ml-3 flex shrink-0 items-center">
                        <UiIcon :name="'models/' + selected.icon" class="h-4 w-4" />
                    </span>

                    <HeadlessComboboxInput
                        class="relative w-full border-none pr-10 pl-2 text-sm leading-5 font-bold
                            focus:ring-0 focus:outline-none"
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
                    class="absolute inset-y-0 right-0 flex cursor-pointer items-center pr-1"
                >
                    <UiIcon name="FlowbiteChevronDownOutline" class="h-7 w-7" />
                </HeadlessComboboxButton>
            </div>

            <Teleport v-if="teleport" to="body">
                <HeadlessTransitionRoot
                    leave="transition ease-in duration-100"
                    leave-from="opacity-100"
                    leave-to="opacity-0"
                    @after-leave="query = ''"
                >
                    <HeadlessComboboxOptions
                        v-if="!disabled"
                        static
                        class="bg-soft-silk absolute z-40 mt-1 h-fit w-160 rounded-md p-1
                            text-base shadow-lg ring-1 ring-black/5 focus:outline-none"
                        :style="{
                            top: `${menuPosition.top}px`,
                            left: `${menuPosition.left}px`,
                        }"
                    >
                        <RecycleScroller
                            v-if="virtualizedMergedModels.length"
                            :items="virtualizedMergedModels"
                            :item-size="null"
                            :min-item-size="40"
                            key-field="id"
                            class="nowheel max-h-60"
                        >
                            <template #default="{ item: modelRow, index }">
                                <HeadlessComboboxOption
                                    v-slot="{ selected: isSelected, active: isActive }"
                                    :value="modelRow.model"
                                    as="template"
                                >
                                    <UiModelsSelectItem
                                        :model="modelRow.model"
                                        :active="isActive"
                                        :selected="isSelected"
                                        :index="index"
                                        :pinned-models-length="nPinnedModels"
                                        :exacto-models-length="nExactoModels"
                                        :merged-models-length="nMergedModels"
                                        :hide-tool="hideTool"
                                    />
                                </HeadlessComboboxOption>
                            </template>
                        </RecycleScroller>

                        <div
                            v-else
                            class="relative cursor-default px-4 py-2 text-gray-700 select-none"
                        >
                            Nothing found.
                        </div>
                    </HeadlessComboboxOptions>
                </HeadlessTransitionRoot>
            </Teleport>

            <HeadlessTransitionRoot
                v-if="!teleport"
                leave="transition ease-in duration-100"
                leave-from="opacity-100"
                leave-to="opacity-0"
                @after-leave="query = ''"
            >
                <HeadlessComboboxOptions
                    v-if="!disabled"
                    class="bg-soft-silk absolute z-40 mt-1 h-fit w-160 rounded-md p-1 text-base
                        shadow-lg ring-1 ring-black/5 focus:outline-none"
                    :class="{
                        'right-0': to === 'right',
                        'left-0': to === 'left',
                        '-top-64': from === 'top',
                    }"
                >
                    <RecycleScroller
                        v-if="virtualizedMergedModels.length"
                        :items="virtualizedMergedModels"
                        :item-size="null"
                        :min-item-size="40"
                        key-field="id"
                        class="nowheel max-h-60"
                    >
                        <template #default="{ item: modelRow, index }">
                            <HeadlessComboboxOption
                                v-slot="{ selected: isSelected, active: isActive }"
                                :value="modelRow.model"
                                as="template"
                            >
                                <UiModelsSelectItem
                                    :model="modelRow.model"
                                    :active="isActive"
                                    :selected="isSelected"
                                    :index="index"
                                    :pinned-models-length="nPinnedModels"
                                    :exacto-models-length="nExactoModels"
                                    :merged-models-length="nMergedModels"
                                    :hide-tool="hideTool"
                                />
                            </HeadlessComboboxOption>
                        </template>
                    </RecycleScroller>

                    <div v-else class="relative cursor-default px-4 py-2 text-gray-700 select-none">
                        Nothing found.
                    </div>
                </HeadlessComboboxOptions>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped></style>
