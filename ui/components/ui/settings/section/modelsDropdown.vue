<script lang="ts" setup>
import { ModelsDropdownSortBy } from '@/types/enums';

// --- Stores ---
const globalSettingsStore = useSettingsStore();
const modelStore = useModelStore();

// --- State from Stores ---
const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { getModel, sortModels, triggerFilter } = modelStore;

// --- Local State ---
const currentPinnedModelToAdd = ref<string | null>(null);
const isMounded = ref(false);

const sortOptions = [
    { id: ModelsDropdownSortBy.NAME_ASC, name: 'Name (Ascending)' },
    { id: ModelsDropdownSortBy.NAME_DESC, name: 'Name (Descending)' },
    { id: ModelsDropdownSortBy.DATE_ASC, name: 'Date Added (Ascending)' },
    { id: ModelsDropdownSortBy.DATE_DESC, name: 'Date Added (Descending)' },
    // { id: ModelsDropdownSortBy.POPULARITY_ASC, name: 'Popularity (Ascending)' },
    // { id: ModelsDropdownSortBy.POPULARITY_DESC, name: 'Popularity (Descending)' },
];

onMounted(() => {
    isMounded.value = true;
});
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] items-center gap-y-8">
        <label class="flex gap-2" for="general-open-chat-view-on-new-canvas">
            <h3 class="text-stone-gray font-bold">Models Sort</h3>
            <UiSettingsInfobubble>
                The order in which the models are displayed in the select menu.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSelect
            :item-list="sortOptions"
            :selected="modelsDropdownSettings.sortBy"
            @update:item-value="
                (value: ModelsDropdownSortBy) => {
                    modelsDropdownSettings.sortBy = value;
                    sortModels(value);
                }
            "
            class="w-[20rem]"
        ></UiSettingsUtilsSelect>

        <label class="flex gap-2" for="models-select-hide-free-models">
            <h3 class="text-stone-gray font-bold">Hide Free Models</h3>
            <UiSettingsInfobubble>
                Hide free models from the model select menu except for pinned models.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            :state="modelsDropdownSettings.hideFreeModels"
            :set-state="
                (value: boolean) => {
                    modelsDropdownSettings.hideFreeModels = value;
                    triggerFilter();
                }
            "
            id="models-select-hide-free-models"
        ></UiSettingsUtilsSwitch>

        <label class="flex gap-2" for="models-select-hide-paid-models">
            <h3 class="text-stone-gray font-bold">Hide Paid Models</h3>
            <UiSettingsInfobubble>
                Hide paid models from the model select menu except for pinned models.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            :state="modelsDropdownSettings.hidePaidModels"
            :set-state="
                (value: boolean) => {
                    modelsDropdownSettings.hidePaidModels = value;
                    triggerFilter();
                }
            "
            id="models-select-hide-paid-models"
        ></UiSettingsUtilsSwitch>

        <label class="flex gap-2" for="general-open-chat-view-on-new-canvas">
            <h3 class="text-stone-gray font-bold">Pinned Models</h3>
            <UiSettingsInfobubble>
                Pinned models are always displayed at the top of the model select menu. This is
                useful for quickly accessing your favorite models.
            </UiSettingsInfobubble>
        </label>
        <div id="models-default-model" class="flex items-center gap-2">
            <UiModelsSelect
                :model="currentPinnedModelToAdd || ''"
                :setModel="
                    (model: string) => {
                        currentPinnedModelToAdd = model;
                    }
                "
                variant="grey"
                class="h-10 w-[20rem]"
            ></UiModelsSelect>
            <button
                class="bg-stone-gray/10 hover:bg-stone-gray/20 flex cursor-pointer items-center justify-center rounded-2xl
                    p-2 transition-colors duration-200 ease-in-out"
                @click="
                    () => {
                        if (currentPinnedModelToAdd) {
                            modelsDropdownSettings.pinnedModels.push(currentPinnedModelToAdd);
                            currentPinnedModelToAdd = null;
                        }
                    }
                "
            >
                <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-5 w-5" />
            </button>
        </div>

        <ul class="col-span-2 flex w-full flex-wrap gap-2 rounded-2xl p-2" v-if="isMounded">
            <template v-for="(model, index) in modelsDropdownSettings.pinnedModels">
                <li
                    v-for="modelInfo in [getModel(model)]"
                    :key="index"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray relative grid h-20 w-60 grid-cols-[1fr_6fr]
                        rounded-2xl border-2 px-4 py-2"
                >
                    <span
                        v-if="modelInfo?.icon"
                        class="flex h-full translate-y-[1px] items-center self-center"
                    >
                        <UiIcon :name="'models/' + modelInfo.icon" class="h-4 w-4" />
                    </span>
                    <span class="self-center font-bold capitalize">{{
                        modelInfo.id.split('/')[0]
                    }}</span>
                    <span class="col-span-2 capitalize">{{ modelInfo.id.split('/')[1] }}</span>
                    <button
                        class="hover:bg-stone-gray/10 absolute top-2 right-2 flex h-8 w-8 items-center justify-center rounded-full
                            transition-colors duration-200 ease-in-out"
                        @click="
                            () => {
                                modelsDropdownSettings.pinnedModels.splice(index, 1);
                            }
                        "
                    >
                        <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-5 w-5" />
                    </button>
                </li>
            </template>
        </ul>
    </div>
</template>

<style scoped></style>
