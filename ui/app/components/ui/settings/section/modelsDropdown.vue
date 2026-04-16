<script lang="ts" setup>
import {
    getModelDropdownSectionDefinitions,
    normalizeModelDropdownSectionOrder,
} from '@/constants/modelDropdownSections';
import { ModelsDropdownSortBy } from '@/types/enums';

// --- Stores ---
const globalSettingsStore = useSettingsStore();
const modelStore = useModelStore();

// --- State from Stores ---
const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);
const { isReady } = storeToRefs(modelStore);

// --- Actions/Methods from Stores ---
const { getModel, sortModels, triggerFilter } = modelStore;
const {
    connectedSubscriptionProviders,
    hasLoaded: hasLoadedProviderStatuses,
    refreshInferenceProviderStatuses,
} = useInferenceProviderStatuses();

// --- Local State ---
const currentPinnedModelToAdd = ref<string | null>(null);
const pinnedDragSourceIndex = ref<number | null>(null);
const sectionDragSourceIndex = ref<number | null>(null);

// --- Computed ---
const isPinnedDragging = computed(() => pinnedDragSourceIndex.value !== null);
const isSectionDragging = computed(() => sectionDragSourceIndex.value !== null);

const sortOptions = [
    { id: ModelsDropdownSortBy.NAME_ASC, name: 'Name (Ascending)' },
    { id: ModelsDropdownSortBy.NAME_DESC, name: 'Name (Descending)' },
    { id: ModelsDropdownSortBy.DATE_ASC, name: 'Date Added (Ascending)' },
    { id: ModelsDropdownSortBy.DATE_DESC, name: 'Date Added (Descending)' },
];

const orderedSectionDefinitions = computed(() => {
    const sectionDefinitions = new Map(
        getModelDropdownSectionDefinitions().map((section) => [section.id, section]),
    );
    const connectedProviders = new Set(connectedSubscriptionProviders.value);

    return normalizeModelDropdownSectionOrder(modelsDropdownSettings.value.sectionOrder)
        .map((sectionId) => sectionDefinitions.get(sectionId))
        .filter(Boolean)
        .map((section) => ({
            ...section,
            isConnected:
                section.type !== 'subscription' ||
                connectedProviders.has(section.provider),
        }));
});

// --- Methods ---
const movePinnedModelLocal = (fromIndex: number, toIndex: number) => {
    const [movedModel] = modelsDropdownSettings.value.pinnedModels.splice(fromIndex, 1);

    if (!movedModel) {
        return;
    }

    modelsDropdownSettings.value.pinnedModels.splice(toIndex, 0, movedModel);
};

const moveSectionLocal = (fromIndex: number, toIndex: number) => {
    const normalizedOrder = normalizeModelDropdownSectionOrder(modelsDropdownSettings.value.sectionOrder);
    const [movedSection] = normalizedOrder.splice(fromIndex, 1);

    if (!movedSection) {
        return;
    }

    normalizedOrder.splice(toIndex, 0, movedSection);
    modelsDropdownSettings.value.sectionOrder = normalizedOrder;
};

const onPinnedDragStart = (event: DragEvent, index: number) => {
    pinnedDragSourceIndex.value = index;

    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.dropEffect = 'move';
    }
};

const onPinnedDragEnter = (index: number) => {
    if (pinnedDragSourceIndex.value === null || index === pinnedDragSourceIndex.value) {
        return;
    }

    movePinnedModelLocal(pinnedDragSourceIndex.value, index);
    pinnedDragSourceIndex.value = index;
};

const onSectionDragStart = (event: DragEvent, index: number) => {
    sectionDragSourceIndex.value = index;

    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.dropEffect = 'move';
    }
};

const onSectionDragEnter = (index: number) => {
    if (sectionDragSourceIndex.value === null || index === sectionDragSourceIndex.value) {
        return;
    }

    moveSectionLocal(sectionDragSourceIndex.value, index);
    sectionDragSourceIndex.value = index;
};

const onDrop = () => {
    // Prevent default browser behavior and let dragEnd clear drag state.
};

const onPinnedDragEnd = () => {
    pinnedDragSourceIndex.value = null;
};

const onSectionDragEnd = () => {
    sectionDragSourceIndex.value = null;
};

watchEffect(() => {
    const normalizedOrder = normalizeModelDropdownSectionOrder(modelsDropdownSettings.value.sectionOrder);

    if (normalizedOrder.join('|') !== (modelsDropdownSettings.value.sectionOrder ?? []).join('|')) {
        modelsDropdownSettings.value.sectionOrder = normalizedOrder;
    }
});

onMounted(() => {
    if (!hasLoadedProviderStatuses.value) {
        refreshInferenceProviderStatuses().catch((error) => {
            console.error('Failed to load inference provider statuses:', error);
        });
    }
});
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
                    @update:item-value="
                        (value: ModelsDropdownSortBy) => {
                            modelsDropdownSettings.sortBy = value;
                            sortModels(value);
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Dropdown Section Order -->
        <div class="py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Dropdown Section Order</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Drag to reorder pinned models, subscription sections, and the all-models section.
                    Disconnected subscription sections stay configurable here but remain hidden in the
                    selector until connected.
                </p>
            </div>

            <TransitionGroup
                name="list"
                tag="ul"
                class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3"
                :class="{ 'no-transition': isSectionDragging }"
            >
                <li
                    v-for="(section, index) in orderedSectionDefinitions"
                    :key="section.id"
                    class="bg-obsidian/50 border-stone-gray/10 relative flex flex-col justify-center
                        rounded-2xl border-2 px-5 py-3"
                    :class="{
                        'cursor-grab active:cursor-grabbing': true,
                        'border-stone-gray/40 scale-95 border-dashed opacity-40':
                            sectionDragSourceIndex === index,
                    }"
                    draggable="true"
                    @dragstart="onSectionDragStart($event, index)"
                    @drop="onDrop"
                    @dragenter.prevent="onSectionDragEnter(index)"
                    @dragover.prevent
                    @dragend="onSectionDragEnd"
                >
                    <div class="flex items-center gap-4">
                        <span
                            v-if="section.icon"
                            class="bg-anthracite/80 border-stone-gray/10 flex h-10 w-10 items-center
                                justify-center rounded-xl border"
                        >
                            <UiIcon :name="section.icon" class="text-soft-silk h-5 w-5" />
                        </span>
                        <div class="min-w-0 flex-1">
                            <div class="flex items-center gap-2">
                                <span class="text-soft-silk font-bold">{{ section.label }}</span>
                                <span
                                    v-if="section.type === 'subscription'"
                                    class="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                                    :class="
                                        section.isConnected
                                            ? 'bg-green-500/10 text-green-400/90'
                                            : 'bg-stone-gray/8 text-stone-gray/40'
                                    "
                                >
                                    {{ section.isConnected ? 'Connected' : 'Disconnected' }}
                                </span>
                            </div>
                            <p class="text-stone-gray/70 mt-1 text-sm">{{ section.description }}</p>
                        </div>
                    </div>
                </li>
            </TransitionGroup>
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
                        Pinned models always appear first inside their section. Add your favorite
                        models here, then drag cards to set their order.
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
                        to="right"
                        from="bottom"
                        variant="grey"
                        class="h-10 w-80"
                    />
                    <button
                        class="bg-obsidian/20 dark:border-obsidian/50 border-soft-silk/20
                            text-soft-silk/80 hover:bg-obsidian/30 flex h-10 w-10 cursor-pointer
                            items-center justify-center rounded-2xl border-2 transition-colors
                            duration-200 ease-in-out"
                        @click="
                            () => {
                                if (
                                    currentPinnedModelToAdd &&
                                    !modelsDropdownSettings.pinnedModels.includes(
                                        currentPinnedModelToAdd,
                                    )
                                ) {
                                    modelsDropdownSettings.pinnedModels.push(currentPinnedModelToAdd);
                                    currentPinnedModelToAdd = null;
                                }
                            }
                        "
                    >
                        <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-5 w-5" />
                    </button>
                </div>
            </div>

            <TransitionGroup
                v-if="isReady && modelsDropdownSettings.pinnedModels.length"
                name="list"
                tag="ul"
                class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3"
                :class="{ 'no-transition': isPinnedDragging }"
            >
                <template v-for="(model, index) in modelsDropdownSettings.pinnedModels">
                    <li
                        v-for="modelInfo in [getModel(model)]"
                        :key="modelInfo.id"
                        class="bg-obsidian/50 border-stone-gray/10 relative flex flex-col
                            justify-center rounded-2xl border-2 px-5 py-3"
                        :class="{
                            'cursor-grab active:cursor-grabbing': true,
                            'border-stone-gray/40 scale-95 border-dashed opacity-40':
                                pinnedDragSourceIndex === index,
                        }"
                        draggable="true"
                        @dragstart="onPinnedDragStart($event, index)"
                        @drop="onDrop"
                        @dragenter.prevent="onPinnedDragEnter(index)"
                        @dragover.prevent
                        @dragend="onPinnedDragEnd"
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
                            class="hover:bg-stone-gray/10 absolute top-2 right-2 flex h-7 w-7
                                items-center justify-center rounded-full transition-colors
                                duration-200 ease-in-out"
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
            </TransitionGroup>
        </div>
    </div>
</template>

<style scoped>
.list-move,
.list-enter-active,
.list-leave-active {
    transition: all 0.3s ease;
}

.list-enter-from,
.list-leave-to {
    opacity: 0;
    transform: translateY(5px);
}

.list-leave-active {
    position: absolute;
}

.no-transition .list-move,
.no-transition .list-enter-active,
.no-transition .list-leave-active {
    transition: none !important;
}
</style>
