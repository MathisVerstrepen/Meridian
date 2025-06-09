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
const { filteredModels: models } = storeToRefs(modelStore);
const { modelsSettings, modelsDropdownSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;
const { getModel } = modelStore;

// --- Props ---
const props = defineProps<{
    model: string;
    setModel: (model: string) => void;
    variant: 'green' | 'grey' | 'terracotta';
}>();

// --- Local State ---
const selected = ref<ModelInfo | undefined>();
const query = ref<string>('');
const scrollerRef = ref<any>();
const nPinnedModels = ref<number>(0);

// --- Computed Properties ---
// The list of all models filtered by the search query
const filteredModels = computed(() => {
    if (!query.value) return models.value;
    return models.value.filter((model) =>
        model.name.toLowerCase().includes(query.value.toLowerCase()),
    );
});

// The list of pinned models AND all models, both filtered by the search query
const mergedModels = computed(() => {
    const pinned = modelsDropdownSettings.value.pinnedModels
        .map((id) => getModel(id))
        .filter(Boolean)
        .filter((model) => model.name.toLowerCase().includes(query.value.toLowerCase()));

    const unpinned = filteredModels.value.filter(
        (model) => !modelsDropdownSettings.value.pinnedModels.includes(model.id),
    );

    nPinnedModels.value = pinned.length;

    return [...pinned, ...unpinned];
});

// --- Lifecycle Hooks ---
onMounted(() => {
    nextTick(() => {
        // Watch for changes in the selected model and update the model prop accordingly
        watch(
            () => selected.value,
            () => {
                if (!selected.value) return;
                props.setModel(selected.value.id);
                setNeedSave(SavingStatus.NOT_SAVED);
            },
        );

        // Watch for changes in the model prop and set the selected model accordingly
        watch(
            () => props.model,
            (newModels) => {
                selected.value = models.value.find((model) => {
                    if (!newModels) return model.id === modelsSettings.value.defaultModel;
                    return model.id === newModels;
                });
                if (!selected.value) {
                    selected.value = getModel(modelsSettings.value.defaultModel);
                }
            },
            { immediate: true },
        );
    });
});

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
                    'bg-soft-silk/15 border-olive-grove-dark text-olive-grove-dark':
                        variant === 'green',
                    'bg-obsidian/20 border-obsidian/50 text-soft-silk/80': variant === 'grey',
                    'bg-soft-silk/50 border-terracotta-clay-dark text-terracotta-clay-dark':
                        variant === 'terracotta',
                }"
            >
                <div class="flex items-center">
                    <span v-if="selected?.icon" class="ml-3 flex flex-shrink-0 items-center">
                        <UiIcon :name="'models/' + selected.icon" class="h-4 w-4" />
                    </span>

                    <HeadlessComboboxInput
                        class="relative w-full border-none pr-10 pl-2 text-sm leading-5 font-bold focus:ring-0 focus:outline-none"
                        :displayValue="(model: unknown) => (model as ModelInfo).name"
                        @change="query = $event.target.value"
                        :class="{
                            'py-1': variant === 'green' || variant === 'terracotta',
                            'py-2': variant === 'grey',
                        }"
                    />
                </div>
                <HeadlessComboboxButton
                    class="absolute inset-y-0 right-0 flex cursor-pointer items-center pr-1"
                >
                    <UiIcon name="FlowbiteChevronDownOutline" class="h-7 w-7" />
                </HeadlessComboboxButton>
            </div>
            <HeadlessTransitionRoot
                leave="transition ease-in duration-100"
                leaveFrom="opacity-100"
                leaveTo="opacity-0"
                @after-leave="query = ''"
            >
                <HeadlessComboboxOptions
                    class="bg-soft-silk absolute z-20 mt-1 h-fit w-[40rem] rounded-md p-1 text-base shadow-lg ring-1
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
                        <template #default="{ item: model, index, active }">
                            <DynamicScrollerItem :item="model" :active="active" :data-index="index">
                                <HeadlessComboboxOption
                                    :value="model"
                                    as="template"
                                    v-slot="{ selected, active }"
                                >
                                    <UiModelsSelectItem
                                        :model="model"
                                        :active="active"
                                        :selected="selected"
                                        :index="index"
                                        :pinnedModelsLength="nPinnedModels"
                                        :mergedModelsLength="mergedModels.length"
                                    >
                                    </UiModelsSelectItem>
                                </HeadlessComboboxOption>
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
