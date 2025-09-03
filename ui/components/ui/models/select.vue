<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller';
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
}>();

// --- Local State ---
const selected = ref<ModelInfo | undefined>();
const query = ref<string>('');
const scrollerRef = ref<unknown>();

// --- Computed Properties ---
// The list of all models filtered by the search query
const filteredModels = computed(() => {
    if (!query.value) return models.value;
    return models.value.filter((model) =>
        model.name.toLowerCase().includes(query.value.toLowerCase()),
    );
});

const pinnedModels = computed(() => {
    if (!isReady.value) return [];
    return modelsDropdownSettings.value.pinnedModels
        .map((id) => getModel(id))
        .filter(Boolean)
        .filter((model) => model.name.toLowerCase().includes(query.value.toLowerCase()));
});

const nPinnedModels = computed(() => pinnedModels.value.length);

// The list of pinned models AND all models, both filtered by the search query
const mergedModels = computed(() => {
    if (!isReady.value) {
        return [];
    }

    const unpinned = filteredModels.value.filter(
        (model) => !modelsDropdownSettings.value.pinnedModels.includes(model.id),
    );

    return [...pinnedModels.value, ...unpinned];
});

// --- Watchers ---
watchEffect(() => {
    if (!isReady.value) {
        return; // Halt execution until the store is ready
    }

    const targetModelId = props.model || modelsSettings.value.defaultModel;
    selected.value =
        models.value.find((model) => model.id === targetModelId) ||
        getModel(modelsSettings.value.defaultModel);
});

watch(selected, (newSelected) => {
    if (!newSelected) return;

    if (props.model !== newSelected.id) {
        props.setModel(newSelected.id);
    }

    setNeedSave(SavingStatus.NOT_SAVED);
});

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

function initializeSelectedModel() {
    const initialModel =
        models.value.find((model) => model.id === props.model) ||
        getModel(modelsSettings.value.defaultModel);
    if (initialModel) {
        selected.value = initialModel;
        props.setModel(initialModel.id);
    }
}

onBeforeUnmount(() => {
    scrollerRef.value = null;
});
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative">
            <div
                class="relative h-full w-full cursor-default overflow-hidden rounded-2xl border-2 text-left
                    focus:outline-none"
                :class="{
                    'bg-soft-silk/15 border-olive-grove-dark dark:text-olive-grove-dark text-anthracite':
                        variant === 'green',
                    'bg-obsidian/20 dark:border-obsidian/50 border-soft-silk/20 text-soft-silk/80':
                        variant === 'grey',
                    [`dark:bg-soft-silk/50 border-terracotta-clay-dark dark:text-terracotta-clay-dark text-anthracite
                    bg-[#612411]/50`]: variant === 'terracotta',
                    'cursor-not-allowed opacity-50': disabled,
                }"
            >
                <div class="flex items-center">
                    <span v-if="selected?.icon" class="ml-3 flex flex-shrink-0 items-center">
                        <UiIcon :name="'models/' + selected.icon" class="h-4 w-4" />
                    </span>

                    <HeadlessComboboxInput
                        class="relative w-full border-none pr-10 pl-2 text-sm leading-5 font-bold focus:ring-0 focus:outline-none"
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
            <HeadlessTransitionRoot
                leave="transition ease-in duration-100"
                leave-from="opacity-100"
                leave-to="opacity-0"
                @after-leave="query = ''"
            >
                <HeadlessComboboxOptions
                    v-if="!disabled"
                    class="bg-soft-silk absolute z-40 mt-1 h-fit w-[40rem] rounded-md p-1 text-base shadow-lg ring-1
                        ring-black/5 focus:outline-none"
                >
                    <DynamicScroller
                        v-if="mergedModels.length"
                        ref="scrollerRef"
                        :items="mergedModels"
                        :min-item-size="40"
                        key-field="id"
                        class="nowheel max-h-60"
                    >
                        <template #default="{ item: modelItem, index, active }">
                            <DynamicScrollerItem
                                :item="modelItem"
                                :active="active"
                                :data-index="index ?? -1"
                            >
                                <template v-if="typeof index === 'number'">
                                    <HeadlessComboboxOption
                                        v-slot="{ selected: isSelected, active: isActive }"
                                        :value="modelItem"
                                        as="template"
                                    >
                                        <UiModelsSelectItem
                                            :model="modelItem"
                                            :active="isActive"
                                            :selected="isSelected"
                                            :index="index"
                                            :pinned-models-length="nPinnedModels"
                                            :merged-models-length="mergedModels.length"
                                        />
                                    </HeadlessComboboxOption>
                                </template>
                            </DynamicScrollerItem>
                        </template>
                    </DynamicScroller>

                    <div v-else class="relative cursor-default px-4 py-2 text-gray-700 select-none">
                        Nothing found.
                    </div>
                </HeadlessComboboxOptions>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped></style>
