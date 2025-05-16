<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { RecycleScroller } from 'vue-virtual-scroller';
import { SavingStatus } from '@/types/enums';
import type { ModelInfo } from '@/types/model';

// --- Stores ---
const modelStore = useModelStore();
const canvasSaveStore = useCanvasSaveStore();
const globalSettingsStore = useGlobalSettingsStore();

// --- State from Stores ---
const { models } = storeToRefs(modelStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;

// --- Props ---
enum Variants {
    GREEN = 'green',
    GREY = 'grey',
}
const props = defineProps({
    model: {
        type: String,
        required: true,
    },
    setModel: {
        type: Function,
        required: true,
    },
    variant: {
        type: String,
        default: Variants,
    },
});

// --- Local State ---
const selected = ref();
const query = ref('');
const scrollerRef = ref<any>();

// --- Computed Properties ---
const filteredModels = computed(() => {
    if (!query.value) return models.value;
    return models.value.filter((model) =>
        model.name.toLowerCase().includes(query.value.toLowerCase()),
    );
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
                    selected.value = models.value.find(
                        (model) => model.id === modelsSettings.value.defaultModel,
                    );
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
                class="relative h-full w-2/3 cursor-default overflow-hidden rounded-2xl border-2 text-left
                    focus:outline-none"
                :class="{
                    'bg-soft-silk/15 border-olive-grove-dark text-olive-grove-dark':
                        variant === Variants.GREEN,
                    'bg-obsidian/20 border-obsidian/50 text-soft-silk/80':
                        variant === Variants.GREY,
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
                            'py-1': variant === Variants.GREEN,
                            'py-2': variant === Variants.GREY,
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
                    class="bg-soft-silk absolute z-20 mt-1 h-fit w-full rounded-md p-1 text-base shadow-lg ring-1 ring-black/5
                        focus:outline-none"
                >
                    <RecycleScroller
                        v-if="filteredModels.length"
                        ref="scrollerRef"
                        :items="filteredModels"
                        :item-size="40"
                        key-field="id"
                        class="nowheel max-h-60"
                    >
                        <template #default="{ item: model, index }">
                            <HeadlessComboboxOption
                                :value="model"
                                as="template"
                                v-slot="{ selected, active }"
                            >
                                <li
                                    class="relative cursor-pointer rounded-md py-2 pr-4 pl-10 select-none"
                                    :class="{
                                        'bg-olive-grove-dark text-soft-silk/80': active,
                                        'text-obsidian': !active,
                                    }"
                                >
                                    <span
                                        class="block truncate"
                                        :class="{
                                            'font-medium': selected,
                                            'font-normal': !selected,
                                        }"
                                    >
                                        {{ model.name }}
                                    </span>
                                    <span
                                        v-if="model.icon"
                                        class="absolute inset-y-0 left-0 flex items-center pl-2"
                                        :class="{
                                            'text-soft-silk/80': active,
                                            'text-obsidian': !active,
                                        }"
                                    >
                                        <UiIcon :name="'models/' + model.icon" class="h-5 w-5" />
                                    </span>
                                </li>
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
