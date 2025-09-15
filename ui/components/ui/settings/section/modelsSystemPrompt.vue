<script lang="ts" setup>
import { motion, AnimatePresence } from 'motion-v';
import draggable from 'vuedraggable';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Local State ---
const expandedPromptName = ref<string | null>(null);

// --- Methods ---
const toggleExpand = (name: string) => {
    if (expandedPromptName.value === name) {
        expandedPromptName.value = null;
    } else {
        expandedPromptName.value = name;
    }
};
</script>

<template>
    <div>
        <draggable
            v-model="modelsSettings.systemPrompt"
            item-key="name"
            handle=".drag-handle"
            ghost-class="ghost"
            class="space-y-2"
        >
            <template #item="{ element: systemPrompt }">
                <div
                    class="bg-obsidian border-stone-gray/10 overflow-hidden rounded-xl border-2"
                >
                    <!-- Collapsed Row -->
                    <div
                        class="flex cursor-pointer items-center p-4 transition-colors hover:bg-white/5"
                        @click="toggleExpand(systemPrompt.name)"
                    >
                        <div
                            class="drag-handle text-stone-gray/50 hover:text-stone-gray mr-4 cursor-move"
                        >
                            <UiIcon name="MaterialSymbolsDragIndicator" class="h-6 w-6" />
                        </div>
                        <div class="flex-grow">
                            <h3 class="text-soft-silk font-medium">
                                {{ systemPrompt.name }}
                            </h3>
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
                            <div @click.stop>
                                <UiSettingsUtilsSwitch
                                    :state="systemPrompt.enabled"
                                    :set-state="(val: boolean) => (systemPrompt.enabled = val)"
                                />
                            </div>
                            <UiIcon
                                name="LineMdChevronSmallUp"
                                class="text-stone-gray h-6 w-6 transform transition-transform duration-200"
                                :class="{ 'rotate-180': expandedPromptName !== systemPrompt.name }"
                            />
                        </div>
                    </div>

                    <!-- Expanded Content -->
                    <AnimatePresence>
                        <motion.div
                            v-if="expandedPromptName === systemPrompt.name"
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
                </div>
            </template>
        </draggable>
    </div>
</template>

<style scoped></style>
