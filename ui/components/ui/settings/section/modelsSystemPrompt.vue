<script lang="ts" setup>
import { motion, AnimatePresence, Reorder, useDragControls } from 'motion-v';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Composables ---
const { generateId } = useUniqueId();

// --- Local State ---
const expandedPromptId = ref<string | null>(null);
const dragControlsMap = new Map();

const getDragControls = (itemId: string) => {
    if (!dragControlsMap.has(itemId)) {
        dragControlsMap.set(itemId, useDragControls());
    }
    return dragControlsMap.get(itemId);
};

// --- Methods ---
const toggleExpand = (id: string) => {
    expandedPromptId.value = expandedPromptId.value === id ? null : id;
};

const addSystemPrompt = () => {
    let newName = 'New System Prompt';
    let counter = 1;
    const existingNames = modelsSettings.value.systemPrompt.map((p) => p.name);
    while (existingNames.includes(newName)) {
        newName = `New System Prompt ${counter}`;
        counter++;
    }

    modelsSettings.value.systemPrompt.push({
        id: generateId(),
        name: newName,
        prompt: '',
        enabled: true,
        editable: true,
        reference: null,
    });
};

const removeSystemPrompt = (index: number) => {
    modelsSettings.value.systemPrompt.splice(index, 1);
};
</script>

<template>
    <div class="flex flex-col">
        <div class="pt-6 pb-4">
            <h3 class="text-soft-silk font-semibold">Global System Prompts</h3>
            <p class="text-stone-gray/80 mt-1 text-sm">
                Manage the global system prompts that are prepended to your conversations. You can
                reorder them by dragging, enable or disable them, and edit their content. The order
                here determines the order of injection.
            </p>
        </div>

        <div class="mt-4">
            <Reorder.Group v-model:values="modelsSettings.systemPrompt" axis="y" class="space-y-2">
                <Reorder.Item
                    v-for="(systemPrompt, index) in modelsSettings.systemPrompt"
                    :key="systemPrompt.id"
                    :value="systemPrompt"
                    :data-index="index"
                    :drag-listener="false"
                    :drag-controls="getDragControls(systemPrompt.id)"
                    class="bg-obsidian/50 border-stone-gray/10 hover:bg-obsidian overflow-hidden rounded-xl border-2
                        transition-colors duration-200 ease-in-out"
                >
                    <!-- Collapsed Row -->
                    <div
                        class="flex cursor-pointer items-center pr-4"
                        @click="toggleExpand(systemPrompt.id)"
                    >
                        <!-- Drag Handle -->
                        <div
                            class="drag-handle no-select text-stone-gray/50 hover:text-stone-gray reorder-handle cursor-move p-4"
                            @pointerdown="(e) => getDragControls(systemPrompt.id).start(e)"
                            @click.stop
                        >
                            <UiIcon name="MaterialSymbolsDragIndicator" class="h-6 w-6" />
                        </div>

                        <!-- Prompt Name -->
                        <div class="flex-grow">
                            <input
                                v-model="systemPrompt.name"
                                :disabled="!systemPrompt.editable"
                                type="text"
                                class="text-soft-silk rounded-md bg-transparent p-1 font-medium focus:bg-white/5 focus:outline-none
                                    disabled:cursor-default"
                                placeholder="Prompt name"
                                :style="{ width: `max(${systemPrompt.name.length + 1}ch, 25ch)` }"
                                @click.stop
                            />
                        </div>

                        <div class="ml-4 flex shrink-0 items-center gap-4">
                            <!-- Editable Indicator -->
                            <span
                                :class="[
                                    systemPrompt.editable
                                        ? 'bg-olive-grove/20 text-olive-grove'
                                        : 'bg-stone-gray/20 text-stone-gray',
                                ]"
                                class="rounded-full px-3 py-1 text-xs font-semibold"
                            >
                                {{ systemPrompt.editable ? 'Editable' : 'Read-only' }}
                            </span>

                            <!-- Delete Button -->
                            <button
                                v-if="systemPrompt.editable"
                                class="text-stone-gray hover:text-terracotta-clay hover:bg-stone-gray/5 flex h-8 w-8 items-center
                                    justify-center rounded-full transition-colors"
                                @click.stop="removeSystemPrompt(index)"
                            >
                                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5" />
                            </button>

                            <!-- Enable/Disable Toggle -->
                            <div @click.stop>
                                <UiSettingsUtilsSwitch
                                    :state="systemPrompt.enabled"
                                    :set-state="(val: boolean) => (systemPrompt.enabled = val)"
                                />
                            </div>

                            <!-- Expand/Collapse Icon -->
                            <UiIcon
                                name="LineMdChevronSmallUp"
                                class="text-stone-gray h-6 w-6 transform transition-transform duration-200"
                                :class="{ 'rotate-180': expandedPromptId !== systemPrompt.id }"
                            />
                        </div>
                    </div>

                    <!-- Expanded Content -->
                    <AnimatePresence>
                        <motion.div
                            v-if="expandedPromptId === systemPrompt.id"
                            key="prompt-content"
                            :initial="{ height: 0, opacity: 0 }"
                            :animate="{
                                height: 'auto',
                                opacity: 1,
                                transition: { duration: 0.3, ease: 'easeOut' },
                            }"
                            :exit="{
                                height: 0,
                                opacity: 0,
                                transition: { duration: 0.2, ease: 'easeIn' },
                            }"
                            class="overflow-hidden"
                        >
                            <div class="px-4 pt-2 pb-4">
                                <textarea
                                    v-model="systemPrompt.prompt"
                                    :disabled="!systemPrompt.editable"
                                    class="custom_scroll bg-anthracite/75 border-stone-gray/20 text-soft-silk focus:border-ember-glow
                                        focus:ring-ember-glow block h-40 w-full rounded-md border p-2 text-sm disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    placeholder="Enter system prompt..."
                                ></textarea>
                            </div>
                        </motion.div>
                    </AnimatePresence>
                </Reorder.Item>
            </Reorder.Group>
            <div class="mt-4">
                <button
                    class="text-soft-silk/80 mt-6 flex cursor-pointer items-center gap-2 rounded-md bg-white/5 px-3 py-2
                        text-sm font-medium transition-colors hover:bg-white/10"
                    @click="addSystemPrompt"
                >
                    <UiIcon name="Fa6SolidPlus" class="h-4 w-4" />
                    Add New System Prompt
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.drag-handle,
.no-select,
.reorder-item-dragging,
.reorder-item-dragging * {
    -webkit-user-select: none !important;
    -moz-user-select: none !important;
    -ms-user-select: none !important;
    user-select: none !important;
}
</style>
