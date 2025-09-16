<script lang="ts" setup>
import { ModelsDropdownSortBy } from '@/types/enums';

// --- Stores ---
const globalSettingsStore = useSettingsStore();
const modelStore = useModelStore();

// --- State from Stores ---
const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);
const { isReady } = storeToRefs(modelStore);

// --- Actions/Methods from Stores ---
const { getModel, sortModels, triggerFilter } = modelStore;

// --- Local State ---
const currentPinnedModelToAdd = ref<string | null>(null);

const sortOptions = [
    { id: ModelsDropdownSortBy.NAME_ASC, name: 'Name (Ascending)' },
    { id: ModelsDropdownSortBy.NAME_DESC, name: 'Name (Descending)' },
    { id: ModelsDropdownSortBy.DATE_ASC, name: 'Date Added (Ascending)' },
    { id: ModelsDropdownSortBy.DATE_DESC, name: 'Date Added (Descending)' },
];
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Models Sort -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Sort Models By</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose the default order for models displayed in selection dropdowns.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSelect
                    :item-list="sortOptions"
                    :selected="modelsDropdownSettings.sortBy"
                    class="w-64"
                    @update:item-value="
                        (value: ModelsDropdownSortBy) => {
                            modelsDropdownSettings.sortBy = value;
                            sortModels(value);
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Hide Free Models -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Hide Free Models</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Enable this to hide free models from the model selection dropdowns. Pinned
                    models will still be visible.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="models-select-hide-free-models"
                    :state="modelsDropdownSettings.hideFreeModels"
                    :set-state="
                        (value: boolean) => {
                            modelsDropdownSettings.hideFreeModels = value;
                            triggerFilter();
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Hide Paid Models -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Hide Paid Models</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Enable this to hide paid models from model selection dropdowns. Pinned models
                    will still be visible.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="models-select-hide-paid-models"
                    :state="modelsDropdownSettings.hidePaidModels"
                    :set-state="
                        (value: boolean) => {
                            modelsDropdownSettings.hidePaidModels = value;
                            triggerFilter();
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Pinned Models -->
        <div class="py-6">
            <div class="flex items-center justify-between">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">Pinned Models</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        Pinned models always appear at the top of selection dropdowns for quick
                        access. Add your favorite models here.
                    </p>
                </div>
                <div id="models-default-model" class="ml-6 flex shrink-0 items-center gap-2">
                    <UiModelsSelect
                        :model="currentPinnedModelToAdd || ''"
                        :set-model="
                            (model: string) => {
                                currentPinnedModelToAdd = model;
                            }
                        "
                        :disabled="false"
                        variant="grey"
                        class="h-10 w-80"
                    />
                    <button
                        class="bg-obsidian/20 dark:border-obsidian/50 border-soft-silk/20 text-soft-silk/80 hover:bg-obsidian/30
                            flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl border-2 transition-colors
                            duration-200 ease-in-out"
                        @click="
                            () => {
                                if (
                                    currentPinnedModelToAdd &&
                                    !modelsDropdownSettings.pinnedModels.includes(
                                        currentPinnedModelToAdd,
                                    )
                                ) {
                                    modelsDropdownSettings.pinnedModels.push(
                                        currentPinnedModelToAdd,
                                    );
                                    currentPinnedModelToAdd = null;
                                }
                            }
                        "
                    >
                        <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-5 w-5" />
                    </button>
                </div>
            </div>

            <ul
                v-if="isReady && modelsDropdownSettings.pinnedModels.length"
                class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3"
            >
                <template v-for="(model, index) in modelsDropdownSettings.pinnedModels">
                    <li
                        v-for="modelInfo in [getModel(model)]"
                        :key="modelInfo.id"
                        class="bg-obsidian/50 border-stone-gray/10 relative flex flex-col justify-center rounded-2xl border-2 px-5
                            py-3"
                    >
                        <div class="flex items-center gap-5">
                            <span v-if="modelInfo?.icon" class="flex items-center">
                                <UiIcon
                                    :name="'models/' + modelInfo.icon"
                                    class="text-stone-gray h-5 w-5"
                                />
                            </span>
                            <div class="flex flex-col">
                                <span class="text-soft-silk font-bold capitalize">{{
                                    modelInfo.id.split('/')[0]
                                }}</span>
                                <span class="text-stone-gray text-sm capitalize">{{
                                    modelInfo.id.split('/')[1]
                                }}</span>
                            </div>
                        </div>
                        <button
                            class="hover:bg-stone-gray/10 absolute top-2 right-2 flex h-7 w-7 items-center justify-center rounded-full
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
    </div>
</template>

<style scoped></style>
