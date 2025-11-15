<script lang="ts" setup>
import { motion } from 'motion-v';
import type { PromptTemplate } from '@/types/settings';

// --- Composables ---
const graphEvents = useGraphEvents();
const { createPromptTemplate, updatePromptTemplate } = useAPI();
const { success, error } = useToast();

// --- Local State ---
const isOpen = ref(false);
const currentTemplate = ref<Partial<PromptTemplate>>({});
const isEditing = computed(() => !!currentTemplate.value.id);

// --- Computed Properties ---
const detectedVariables = computed(() => {
    if (!currentTemplate.value.templateText) return [];
    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const matches = currentTemplate.value.templateText.matchAll(regex);
    const variables = new Set(Array.from(matches, (m) => m[1]));
    return Array.from(variables);
});

// --- Methods ---
const openEditor = (data: { template?: PromptTemplate }) => {
    if (data.template) {
        currentTemplate.value = JSON.parse(JSON.stringify(data.template));
    } else {
        currentTemplate.value = {
            name: '',
            description: '',
            templateText: '',
            isPublic: false,
        };
    }
    isOpen.value = true;
};

const closeEditor = () => {
    isOpen.value = false;
    setTimeout(() => {
        currentTemplate.value = {};
    }, 300);
};

const handleSave = async () => {
    if (!currentTemplate.value.name?.trim() || !currentTemplate.value.templateText?.trim()) {
        error('Template name and content cannot be empty.');
        return;
    }

    try {
        if (isEditing.value) {
            await updatePromptTemplate(currentTemplate.value.id!, {
                name: currentTemplate.value.name,
                description: currentTemplate.value.description,
                templateText: currentTemplate.value.templateText,
                isPublic: currentTemplate.value.isPublic,
            });
            success('Template updated successfully.');
        } else {
            await createPromptTemplate({
                name: currentTemplate.value.name!,
                description: currentTemplate.value.description,
                templateText: currentTemplate.value.templateText!,
                isPublic: currentTemplate.value.isPublic!,
            });
            success('Template created successfully.');
        }
        graphEvents.emit('prompt-template-saved', {});
        closeEditor();
    } catch (err) {
        console.error('Failed to save template:', err);
        error('An error occurred while saving the template.');
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('open-prompt-template-editor', openEditor);

    const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape' && isOpen.value) {
            closeEditor();
        }
    };
    window.addEventListener('keydown', handleKeyDown);

    onUnmounted(() => {
        unsubscribe();
        window.removeEventListener('keydown', handleKeyDown);
    });
});
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-if="isOpen"
            key="prompt-template-editor"
            :initial="{ opacity: 0 }"
            :animate="{ opacity: 1, transition: { duration: 0.3, ease: 'easeOut' } }"
            :exit="{ opacity: 0, transition: { duration: 0.2, ease: 'easeIn' } }"
            class="bg-anthracite/25 fixed inset-0 z-[25] flex items-center justify-center p-4
                backdrop-blur-lg sm:p-6 md:p-8"
            @click.self="closeEditor"
        >
            <motion.div
                :initial="{ opacity: 0, scale: 0.95 }"
                :animate="{ opacity: 1, scale: 1, transition: { duration: 0.3, ease: 'easeOut' } }"
                :exit="{ opacity: 0, scale: 0.95, transition: { duration: 0.2, ease: 'easeIn' } }"
                class="bg-obsidian/50 border-stone-gray/10 grid h-full w-full max-w-7xl
                    grid-rows-[auto_1fr_auto] gap-6 overflow-hidden rounded-2xl border p-6"
            >
                <!-- Header -->
                <div class="col-span-1 flex items-center justify-between">
                    <h2 class="text-soft-silk text-2xl font-bold">
                        {{ isEditing ? 'Edit' : 'Create' }} Prompt Template
                    </h2>
                    <button
                        class="hover:bg-stone-gray/10 flex h-10 w-10 items-center justify-center
                            rounded-full transition-colors"
                        aria-label="Close editor"
                        @click="closeEditor"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
                    </button>
                </div>

                <!-- Main Content Grid -->
                <div class="grid h-full min-h-0 grid-cols-1 gap-6 lg:grid-cols-3">
                    <!-- Left Panel: Editor -->
                    <div
                        class="custom_scroll flex h-full min-h-0 flex-col gap-6 overflow-y-auto pr-2
                            lg:col-span-2"
                    >
                        <div class="flex flex-col gap-2">
                            <label class="text-stone-gray text-sm font-medium">Template Name</label>
                            <input
                                v-model="currentTemplate.name"
                                type="text"
                                placeholder="e.g., README Generator"
                                class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                    focus:border-soft-silk/30 block w-full rounded-lg border-2 p-2.5
                                    text-base outline-none focus:ring-0"
                                required
                            />
                        </div>
                        <div class="flex flex-col gap-2">
                            <label class="text-stone-gray text-sm font-medium"
                                >Description (Optional)</label
                            >
                            <textarea
                                v-model="currentTemplate.description"
                                rows="3"
                                placeholder="A short description of what this template does."
                                class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                    focus:border-soft-silk/30 block w-full rounded-lg border-2 p-2.5
                                    text-sm outline-none focus:ring-0"
                            ></textarea>
                        </div>
                        <div class="flex flex-1 flex-col gap-2">
                            <label
                                class="text-stone-gray flex items-center gap-2 text-sm font-medium"
                            >
                                Template Content
                                <UiSettingsInfobubble direction="left">
                                    <p class="font-semibold">How to define variables:</p>
                                    <p class="mt-1 text-sm">
                                        Use double curly braces for variables, like
                                        <code
                                            class="bg-obsidian/50 rounded px-1 py-0.5 font-mono
                                                text-xs"
                                            >&lbrace;&lbrace;variable_name&rbrace;&rbrace;</code
                                        >.
                                    </p>
                                </UiSettingsInfobubble>
                            </label>
                            <textarea
                                v-model="currentTemplate.templateText"
                                placeholder="Based on this code sample: {{code_sample}}..."
                                class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                    focus:border-soft-silk/30 custom_scroll flex-grow resize-none
                                    rounded-lg border-2 p-3 font-mono text-sm outline-none
                                    focus:ring-0"
                                required
                            ></textarea>
                        </div>
                    </div>

                    <!-- Right Panel: Sidebar -->
                    <div
                        class="bg-obsidian custom_scroll border-stone-gray/10 flex h-full min-h-0
                            flex-col gap-6 overflow-y-auto rounded-lg border p-4"
                    >
                        <div>
                            <h3 class="text-soft-silk font-semibold">Configuration</h3>
                            <div class="mt-4 flex items-center justify-between">
                                <label
                                    for="is-public-toggle"
                                    class="text-stone-gray text-sm font-medium"
                                >
                                    Public Template
                                    <p class="text-stone-gray/60 text-xs">
                                        Allow other users to use this template.
                                    </p>
                                </label>
                                <HeadlessSwitch
                                    id="is-public-toggle"
                                    v-model="currentTemplate.isPublic"
                                    :class="
                                        currentTemplate.isPublic
                                            ? 'bg-ember-glow'
                                            : 'bg-stone-gray/20'
                                    "
                                    class="relative inline-flex h-6 w-11 items-center rounded-full
                                        transition-colors"
                                >
                                    <span
                                        :class="
                                            currentTemplate.isPublic
                                                ? 'translate-x-6'
                                                : 'translate-x-1'
                                        "
                                        class="inline-block h-4 w-4 transform rounded-full bg-white
                                            transition-transform"
                                    />
                                </HeadlessSwitch>
                            </div>
                        </div>
                        <div class="border-stone-gray/20 h-px w-full border-t"></div>
                        <div>
                            <h3 class="text-soft-silk font-semibold">Detected Variables</h3>
                            <div v-if="detectedVariables.length" class="mt-3 flex flex-wrap gap-2">
                                <span
                                    v-for="variable in detectedVariables"
                                    :key="variable"
                                    class="bg-slate-blue/20 text-slate-blue-dark dark:text-soft-silk
                                        rounded-md px-2 py-1 font-mono text-xs font-medium"
                                >
                                    {{ variable }}
                                </span>
                            </div>
                            <p v-else class="text-stone-gray/60 mt-3 text-sm">
                                No variables found. Add variables like
                                <code class="bg-obsidian/50 rounded px-1 py-0.5 font-mono text-xs"
                                    >&lbrace;&lbrace;variable_name&rbrace;&rbrace;</code
                                >
                                in the content.
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Footer -->
                <div class="col-span-1 flex items-center justify-end gap-3">
                    <button
                        type="button"
                        class="hover:bg-stone-gray/10 text-soft-silk rounded-lg px-4 py-2 text-sm
                            font-bold transition-colors"
                        @click="closeEditor"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        class="bg-ember-glow hover:bg-ember-glow/80 text-soft-silk rounded-lg px-5
                            py-2 text-sm font-bold transition-colors"
                        @click="handleSave"
                    >
                        Save Template
                    </button>
                </div>
            </motion.div>
        </motion.div>
    </AnimatePresence>
</template>
