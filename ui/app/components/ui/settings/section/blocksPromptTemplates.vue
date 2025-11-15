<script lang="ts" setup>
import type { PromptTemplate } from '@/types/settings';

// --- Composables ---
const { getPromptTemplates, createPromptTemplate, updatePromptTemplate, deletePromptTemplate } =
    useAPI();
const { success, error } = useToast();

// --- Local State ---
const promptTemplates = ref<PromptTemplate[]>([]);
const isTemplateModalOpen = ref(false);
const currentTemplate = ref<Partial<PromptTemplate>>({});
const isEditingTemplate = computed(() => !!currentTemplate.value.id);

// --- Methods ---
const fetchTemplates = async () => {
    try {
        promptTemplates.value = await getPromptTemplates();
    } catch {
        error('Failed to load prompt templates.');
    }
};

const openCreateModal = () => {
    currentTemplate.value = {
        name: '',
        description: '',
        templateText: '',
    };
    isTemplateModalOpen.value = true;
};

const openEditModal = (template: PromptTemplate) => {
    currentTemplate.value = { ...template };
    isTemplateModalOpen.value = true;
};

const handleSaveTemplate = async () => {
    if (!currentTemplate.value.name || !currentTemplate.value.templateText) {
        error('Template name and text are required.');
        return;
    }

    try {
        if (isEditingTemplate.value) {
            await updatePromptTemplate(currentTemplate.value.id!, {
                name: currentTemplate.value.name,
                description: currentTemplate.value.description,
                templateText: currentTemplate.value.templateText,
            });
            success('Template updated successfully.');
        } else {
            await createPromptTemplate({
                name: currentTemplate.value.name!,
                description: currentTemplate.value.description,
                templateText: currentTemplate.value.templateText!,
            });
            success('Template created successfully.');
        }
        isTemplateModalOpen.value = false;
        await fetchTemplates();
    } catch {
        error(`Failed to save template.`);
    }
};

const handleDeleteTemplate = async (templateId: string) => {
    if (confirm('Are you sure you want to delete this template?')) {
        try {
            await deletePromptTemplate(templateId);
            success('Template deleted successfully.');
            await fetchTemplates();
        } catch {
            error('Failed to delete template.');
        }
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    fetchTemplates();
});
</script>

<template>
    <div class="py-6">
        <div class="mb-4 flex items-center justify-between">
            <div>
                <h3 class="text-soft-silk font-semibold">Manage your prompt templates</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Create and manage reusable prompt templates for your nodes.
                </p>
            </div>
            <button
                class="bg-ember-glow hover:bg-ember-glow/80 text-soft-silk rounded-lg px-4 py-2
                    text-sm font-bold transition-colors"
                @click="openCreateModal"
            >
                Create Template
            </button>
        </div>
        <div class="mt-8">
            <div v-if="!promptTemplates.length" class="text-stone-gray/60 py-12 text-center">
                You don't have any templates yet.
            </div>
            <ul v-else class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
                <UiLibraryPromptCard
                    v-for="template in promptTemplates"
                    :key="template.id"
                    :template="template"
                    @open-edit-modal="openEditModal"
                    @delete-template="handleDeleteTemplate"
                />
            </ul>
        </div>

        <!-- Prompt Template Modal -->
        <HeadlessTransitionRoot :show="isTemplateModalOpen" as="template">
            <HeadlessDialog class="relative z-50" @close="isTemplateModalOpen = false">
                <HeadlessTransitionChild
                    as="template"
                    enter="duration-300 ease-out"
                    enter-from="opacity-0"
                    enter-to="opacity-100"
                    leave="duration-200 ease-in"
                    leave-from="opacity-100"
                    leave-to="opacity-0"
                >
                    <div class="bg-obsidian/60 fixed inset-0 backdrop-blur-sm" aria-hidden="true" />
                </HeadlessTransitionChild>
                <div class="fixed inset-0 flex items-center justify-center p-4">
                    <HeadlessTransitionChild
                        as="template"
                        enter="duration-300 ease-out"
                        enter-from="opacity-0 scale-95"
                        enter-to="opacity-100 scale-100"
                        leave="duration-200 ease-in"
                        leave-from="opacity-100 scale-100"
                        leave-to="opacity-0 scale-95"
                    >
                        <HeadlessDialogPanel
                            class="bg-anthracite border-stone-gray/10 w-full max-w-2xl rounded-2xl
                                border p-6"
                        >
                            <HeadlessDialogTitle class="text-soft-silk text-lg font-semibold">
                                {{ isEditingTemplate ? 'Edit' : 'Create' }} Prompt Template
                            </HeadlessDialogTitle>
                            <form
                                class="mt-4 flex flex-col gap-4"
                                @submit.prevent="handleSaveTemplate"
                            >
                                <div>
                                    <label class="text-stone-gray text-sm font-medium"
                                        >Template Name</label
                                    >
                                    <input
                                        v-model="currentTemplate.name"
                                        type="text"
                                        class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                                            focus:border-ember-glow mt-1 block w-full rounded-lg
                                            border-2 p-2 focus:ring-0"
                                        required
                                    />
                                </div>
                                <div>
                                    <label class="text-stone-gray text-sm font-medium"
                                        >Description (Optional)</label
                                    >
                                    <input
                                        v-model="currentTemplate.description"
                                        type="text"
                                        class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                                            focus:border-ember-glow mt-1 block w-full rounded-lg
                                            border-2 p-2 focus:ring-0"
                                    />
                                </div>
                                <div>
                                    <label
                                        class="text-stone-gray flex items-center gap-2 text-sm
                                            font-medium"
                                        >Template Text
                                        <UiSettingsInfobubble direction="right">
                                            <p class="font-semibold">How to define variables:</p>
                                            <p class="mt-1 text-sm">
                                                Use double curly braces to define a variable, like
                                                <code
                                                    class="bg-obsidian/50 rounded px-1 py-0.5
                                                        font-mono text-xs"
                                                    >&lbrace;&lbrace;variable_name&rbrace;&rbrace;</code
                                                >.
                                            </p>
                                            <p class="mt-2 text-sm">
                                                Each variable will become a separate text input on
                                                the prompt node.
                                            </p>
                                        </UiSettingsInfobubble>
                                    </label>
                                    <textarea
                                        v-model="currentTemplate.templateText"
                                        rows="6"
                                        class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                                            focus:border-ember-glow mt-1 block w-full rounded-lg
                                            border-2 p-2 font-mono text-sm focus:ring-0"
                                        required
                                    ></textarea>
                                </div>
                                <div class="mt-4 flex justify-end gap-2">
                                    <button
                                        type="button"
                                        class="hover:bg-stone-gray/10 text-soft-silk rounded-lg px-4
                                            py-2 text-sm font-bold transition-colors"
                                        @click="isTemplateModalOpen = false"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        class="bg-ember-glow hover:bg-ember-glow/80 text-soft-silk
                                            rounded-lg px-4 py-2 text-sm font-bold
                                            transition-colors"
                                    >
                                        Save Template
                                    </button>
                                </div>
                            </form>
                        </HeadlessDialogPanel>
                    </HeadlessTransitionChild>
                </div>
            </HeadlessDialog>
        </HeadlessTransitionRoot>
    </div>
</template>
