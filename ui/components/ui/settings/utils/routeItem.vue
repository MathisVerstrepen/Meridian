<script lang="ts" setup>
import type { Route } from '@/types/settings';

const props = defineProps<{
    route: Route;
    isLocked: boolean;
}>();

const emit = defineEmits<{
    (e: 'update-route', payload: Route): void;
    (e: 'delete-route', id: string): void;
}>();

// --- Stores ---
const modelStore = useModelStore();

// --- Actions/Methods from Stores ---
const { getModel } = modelStore;

// --- Local State ---
const isEditing = ref(false);
const editableRoute = ref<Route | null>(null);
const containerRef = ref<HTMLElement | null>(null);
const contentRef = ref<HTMLElement | null>(null);

const availableIcons = [
    'routes/StreamlineChatBubbleTypingOvalSolid',
    'routes/IonCodeSlash',
    'routes/Fa6SolidPenFancy',
    'routes/PhMagnifyingGlassBold',
    'routes/GravityUiFileZipper',
    'routes/IconParkOutlineBrain',
    'routes/MaterialSymbolsEmojiLanguageOutline',
    'routes/MaterialSymbolsElectricBoltRounded',
];

// --- Core Logic ---
const startEditing = () => {
    editableRoute.value = JSON.parse(JSON.stringify(props.route));
    isEditing.value = true;
};

const cancelEditing = () => {
    isEditing.value = false;
    editableRoute.value = null;
};

const saveChanges = () => {
    if (editableRoute.value) {
        emit('update-route', editableRoute.value);
    }
    isEditing.value = false;
};

const deleteRoute = () => {
    emit('delete-route', props.route.id);
};

const selectIcon = (icon: string) => {
    if (editableRoute.value) {
        editableRoute.value.icon = icon;
    }
};

const updateContainerHeight = async () => {
    await nextTick();
    if (containerRef.value && contentRef.value) {
        containerRef.value.style.height = `${contentRef.value.scrollHeight}px`;
    }
};

watch(isEditing, updateContainerHeight, { immediate: true });
</script>

<template>
    <div
        ref="containerRef"
        class="bg-obsidian w-full shrink-0 overflow-hidden rounded-xl shadow-md transition-[height] duration-300
            ease-in-out"
    >
        <div ref="contentRef">
            <div
                v-if="!isEditing"
                class="hover:bg-obsidian/75 grid w-full grid-cols-[50px_auto_auto] items-center gap-4 rounded-xl p-4"
            >
                <UiIcon
                    :name="route.icon"
                    class="text-stone-gray h-6 w-6 justify-self-center"
                ></UiIcon>
                <div>
                    <h3 class="text-stone-gray text-lg font-semibold">
                        {{ route.name }}
                    </h3>
                    <p class="text-stone-gray/75 text-sm">{{ route.description }}</p>
                </div>
                <div class="flex flex-col items-end justify-end gap-2">
                    <div class="flex items-center gap-2">
                        <button
                            @click="startEditing"
                            class="bg-stone-gray/10 hover:bg-stone-gray/5 text-stone-gray flex cursor-pointer items-center
                                justify-center rounded-lg p-1 transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                                disabled:opacity-50"
                            :disabled="isLocked"
                        >
                            <UiIcon name="MaterialSymbolsEditRounded" class="h-5 w-5"></UiIcon>
                        </button>
                        <button
                            @click="deleteRoute"
                            class="bg-terracotta-clay/20 hover:bg-terracotta-clay/10 text-terracotta-clay flex cursor-pointer
                                items-center justify-center rounded-lg p-1 transition-colors duration-200 ease-in-out
                                disabled:cursor-not-allowed disabled:opacity-50"
                            :disabled="isLocked"
                        >
                            <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5"></UiIcon>
                        </button>
                    </div>

                    <div
                        class="border-anthracite text-stone-gray/50 flex max-w-[200px] items-center gap-1 rounded-lg border px-2
                            py-1 text-xs font-bold"
                        v-for="modelInfo in [getModel(route.modelId)]"
                        :title="modelInfo.name"
                    >
                        <UiIcon :name="'models/' + modelInfo.icon" class="h-4 w-4 shrink-0" />
                        <span class="truncate">{{ route.modelId }}</span>
                    </div>
                </div>
            </div>

            <!-- Edit Form -->
            <div v-else-if="editableRoute" class="flex w-full flex-col gap-4 rounded-xl p-4">
                <div class="grid grid-cols-2 gap-4">
                    <!-- Name -->
                    <div class="flex flex-col gap-2">
                        <label class="text-stone-gray/75 text-xs font-semibold">Name</label>
                        <input
                            v-model="editableRoute.name"
                            type="text"
                            class="border-stone-gray/20 bg-soft-silk/5 text-stone-gray focus:border-ember-glow h-10 w-[20rem]
                                rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                            placeholder="Route Name"
                            @input="
                                (event: Event) => {
                                    if (!editableRoute) return;
                                    editableRoute.name = (event.target as HTMLInputElement).value;
                                }
                            "
                        />
                    </div>

                    <!-- Icon Select -->
                    <div class="flex flex-col gap-2">
                        <label class="text-stone-gray/75 text-xs font-semibold">Icon</label>
                        <div class="flex items-center gap-2">
                            <UiIcon
                                v-for="icon in availableIcons"
                                :key="icon"
                                :name="icon"
                                class="border-stone-gray/20 hover:bg-stone-gray/10 text-stone-gray h-12 w-12 cursor-pointer rounded-2xl
                                    border p-3 transition-colors duration-200 ease-in-out"
                                :class="{
                                    'bg-ember-glow/10 !border-ember-glow/80 !text-ember-glow/80':
                                        editableRoute.icon === icon,
                                }"
                                @click="selectIcon(icon)"
                            />
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <!-- Description -->
                    <div class="flex flex-col gap-1">
                        <label class="text-stone-gray/75 text-xs font-semibold">Description</label>
                        <textarea
                            v-model="editableRoute.description"
                            :setModel="
                                (value: string) => {
                                    if (!editableRoute) return;
                                    editableRoute.description = value;
                                }
                            "
                            class="border-stone-gray/20 bg-soft-silk/5 text-stone-gray focus:border-ember-glow h-32 w-[30rem]
                                rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                            id="models-global-system-prompt"
                        ></textarea>
                    </div>

                    <!-- Custom Prompt -->
                    <div class="flex flex-col gap-1">
                        <label class="text-stone-gray/75 text-xs font-semibold"
                            >Custom Prompt</label
                        >
                        <textarea
                            v-model="editableRoute.customPrompt"
                            :setModel="
                                (value: string) => {
                                    if (!editableRoute) return;
                                    editableRoute.customPrompt = value;
                                }
                            "
                            class="border-stone-gray/20 bg-soft-silk/5 text-stone-gray focus:border-ember-glow h-32 w-[30rem]
                                rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                            id="models-global-system-prompt"
                        ></textarea>
                    </div>

                    <!-- Model Select -->
                    <div class="flex flex-col gap-2">
                        <label class="text-stone-gray/75 text-xs font-semibold">Model</label>
                        <div class="relative">
                            <UiModelsSelect
                                :model="editableRoute.modelId"
                                :setModel="
                                    (model: string) => {
                                        if (!editableRoute) return;
                                        editableRoute.modelId = model;
                                    }
                                "
                                :disabled="false"
                                variant="grey"
                                class="bg-soft-silk/10 h-10 w-[20rem] rounded-2xl"
                            ></UiModelsSelect>
                        </div>
                    </div>

                    <!-- Override Global Prompt -->
                    <div class="flex items-center gap-2">
                        <UiSettingsUtilsSwitch
                            :state="editableRoute.overrideGlobalPrompt"
                            :set-state="
                                (value: boolean) => {
                                    if (!editableRoute) return;
                                    editableRoute.overrideGlobalPrompt = value;
                                }
                            "
                            :id="`override-${editableRoute.id}`"
                        ></UiSettingsUtilsSwitch>
                        <label
                            :for="`override-${editableRoute.id}`"
                            class="text-stone-gray/75 text-sm select-none"
                        >
                            Override Global Prompt
                        </label>
                    </div>

                    <!-- Action Buttons -->
                    <div class="col-span-2 flex items-center justify-center gap-2 pt-2">
                        <button
                            @click="cancelEditing"
                            class="bg-stone-gray/10 hover:bg-stone-gray/5 text-stone-gray cursor-pointer rounded-lg px-4 py-1.5 text-sm
                                font-semibold transition-colors duration-200 ease-in-out"
                        >
                            Cancel
                        </button>
                        <button
                            @click="saveChanges"
                            class="bg-ember-glow/10 text-ember-glow/80 hover:bg-ember-glow/5 cursor-pointer rounded-lg px-4 py-1.5
                                text-sm font-semibold transition-colors duration-200 ease-in-out"
                        >
                            Save Changes
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
