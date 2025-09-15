<script lang="ts" setup>
import { motion, AnimatePresence, Reorder, useDragControls } from 'motion-v';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Composables ---
const dragControls = useDragControls();
const { generateId } = useUniqueId();

// --- Local State ---
const expandedPromptId = ref<string | null>(null);

// --- Methods ---
const toggleExpand = (id: string) => {
    if (expandedPromptId.value === id   ) {
        expandedPromptId.value = null;
    } else {
        expandedPromptId.value = id;
    }
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
    });
};

const removeSystemPrompt = (index: number) => {
    modelsSettings.value.systemPrompt.splice(index, 1);
};
</script>

<template>
    <div>
        <Reorder.Group v-model:values="modelsSettings.systemPrompt" axis="y">
            <Reorder.Item
                v-for="(systemPrompt, index) in modelsSettings.systemPrompt"
                :key="systemPrompt.id"
                :value="systemPrompt"
                :data-index="index"
                :drag-controls="dragControls"
                class="bg-obsidian border-stone-gray/10 mb-2 overflow-hidden rounded-xl border-2"
            >
                <!-- Collapsed Row -->
                <div
                    class="flex cursor-pointer items-center transition-colors hover:bg-white/5"
                    @click="toggleExpand(systemPrompt.id)"
                >
                    <div
                        class="drag-handle text-stone-gray/50 hover:text-stone-gray cursor-move p-4"
                        @pointerDown.prevent="(e: PointerEvent) => dragControls.start(e)"
                        @click="$event.stopPropagation()"
                    >
                        <UiIcon name="MaterialSymbolsDragIndicator" class="h-6 w-6" />
                    </div>

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

                    <div class="flex items-center gap-4">
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
                        <button
                            v-if="systemPrompt.editable"
                            class="hover:text-scarlet-red flex items-center justify-center rounded-lg p-2 text-red-400
                                transition-colors hover:bg-red-400/5"
                            @click.stop="removeSystemPrompt(index)"
                        >
                            <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5" />
                        </button>
                        <div @click.stop>
                            <UiSettingsUtilsSwitch
                                :state="systemPrompt.enabled"
                                :set-state="(val: boolean) => (systemPrompt.enabled = val)"
                            />
                        </div>
                        <UiIcon
                            name="LineMdChevronSmallUp"
                            class="text-stone-gray mr-4 h-6 w-6 transform transition-transform duration-200"
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
                class="text-soft-silk/80 flex cursor-pointer items-center gap-2 rounded-md bg-white/5 px-3 py-2 text-sm
                    font-medium transition-colors hover:bg-white/10"
                @click="addSystemPrompt"
            >
                <UiIcon name="Fa6SolidPlus" class="h-4 w-4" />
                Add New System Prompt
            </button>
        </div>
    </div>
</template>

<style scoped></style>
