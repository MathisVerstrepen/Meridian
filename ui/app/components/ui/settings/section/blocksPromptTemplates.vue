<script lang="ts" setup>
import type { PromptTemplate } from '@/types/settings';

// --- Composables ---
const { deletePromptTemplate } = useAPI();
const { success, error } = useToast();
const graphEvents = useGraphEvents();
const promptTemplateStore = usePromptTemplateStore();

// --- Computed ---
const promptTemplates = computed(() => promptTemplateStore.userTemplates);

// --- Methods ---
const fetchTemplates = async (force = false) => {
    try {
        await promptTemplateStore.fetchUserTemplates(force);
    } catch {
        error('Failed to load prompt templates.');
    }
};

const openCreateModal = () => {
    graphEvents.emit('open-prompt-template-editor', {});
};

const openEditModal = (template: PromptTemplate) => {
    graphEvents.emit('open-prompt-template-editor', { template });
};

const handleDeleteTemplate = async (templateId: string) => {
    if (confirm('Are you sure you want to delete this template?')) {
        try {
            await deletePromptTemplate(templateId);
            success('Template deleted successfully.');
            // Force refresh to update the list
            await fetchTemplates(true);
        } catch {
            error('Failed to delete template.');
        }
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    fetchTemplates();
    const unsubscribe = graphEvents.on('prompt-template-saved', () => fetchTemplates(true));

    onUnmounted(() => {
        unsubscribe();
    });
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
    </div>
</template>