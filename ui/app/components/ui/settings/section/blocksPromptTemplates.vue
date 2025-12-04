<script lang="ts" setup>
import type { PromptTemplate } from '@/types/settings';

// --- Composables ---
const { success, error } = useToast();
const graphEvents = useGraphEvents();
const promptTemplateStore = usePromptTemplateStore();

// --- Local State ---
const searchQuery = ref('');

// --- Computed ---
const promptTemplates = computed(() => promptTemplateStore.userTemplates);

const filteredTemplates = computed(() => {
    if (!searchQuery.value) return promptTemplates.value;
    const query = searchQuery.value.toLowerCase();
    return promptTemplates.value.filter(
        (t) =>
            t.name.toLowerCase().includes(query) ||
            (t.description && t.description.toLowerCase().includes(query)),
    );
});

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
    if (confirm('Are you sure you want to delete this template? This action cannot be undone.')) {
        try {
            await promptTemplateStore.deleteTemplate(templateId);
            success('Template deleted successfully.');
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
    <div class="flex h-full flex-col py-6">
        <!-- Header Section -->
        <div class="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
                <h3 class="text-soft-silk text-xl font-semibold tracking-tight">
                    Prompt Templates
                </h3>
                <p class="text-stone-gray/80 mt-1 max-w-2xl text-sm leading-relaxed">
                    Create reusable prompt structures with variables (e.g.,
                    <code class="bg-stone-gray/10 rounded px-1 py-0.5 font-mono text-xs"
                        >&lbrace;&lbrace;input&rbrace;&rbrace;</code
                    >) to standardize your workflow nodes.
                </p>
            </div>

            <div class="flex items-center gap-3">
                <!-- Search Input -->
                <div class="relative w-full md:w-64">
                    <UiIcon
                        name="MdiMagnify"
                        class="text-stone-gray absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2
                            opacity-70"
                    />
                    <input
                        v-model="searchQuery"
                        type="text"
                        placeholder="Search templates..."
                        class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                            placeholder:text-stone-gray/40 focus:border-soft-silk/30 block w-full
                            rounded-lg border py-2 pr-4 pl-9 text-sm transition-colors outline-none
                            focus:ring-0"
                    />
                </div>

                <!-- Create Button -->
                <button
                    class="bg-ember-glow hover:bg-ember-glow/90 text-soft-silk shadow-ember-glow/20
                        flex flex-shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-sm font-bold
                        shadow-lg transition-all hover:scale-[1.02] active:scale-[0.98]"
                    @click="openCreateModal"
                >
                    <UiIcon name="Fa6SolidPlus" class="h-4 w-4" />
                    <span class="hidden sm:inline">Create Template</span>
                    <span class="sm:hidden">Create</span>
                </button>
            </div>
        </div>

        <!-- Content Area -->
        <div class="min-h-[300px]">
            <!-- Loading State -->
            <div
                v-if="promptTemplateStore.isLoadingUser && !promptTemplates.length"
                class="flex h-40 items-center justify-center"
            >
                Loading templates...
            </div>

            <!-- Empty State: No Templates Created -->
            <div
                v-else-if="!promptTemplates.length"
                class="border-stone-gray/10 bg-anthracite/10 flex flex-col items-center
                    justify-center rounded-2xl border py-16 text-center"
            >
                <div
                    class="bg-stone-gray/5 mb-4 flex h-16 w-16 items-center justify-center
                        rounded-full"
                >
                    <UiIcon
                        name="MaterialSymbolsTextSnippetOutlineRounded"
                        class="text-stone-gray/40 h-8 w-8"
                    />
                </div>
                <h4 class="text-soft-silk font-medium">No templates yet</h4>
                <p class="text-stone-gray/60 mt-1 max-w-xs text-sm">
                    Get started by creating your first prompt template to speed up your graph
                    building.
                </p>
                <button
                    class="text-ember-glow hover:text-ember-glow/80 mt-4 text-sm font-bold
                        transition-colors"
                    @click="openCreateModal"
                >
                    Create your first template
                </button>
            </div>

            <!-- Empty State: Search returned no results -->
            <div v-else-if="!filteredTemplates.length" class="text-stone-gray/60 py-12 text-center">
                <UiIcon name="MaterialSymbolsSearchOff" class="mx-auto mb-2 h-10 w-10 opacity-50" />
                <p>No templates match your search.</p>
                <button
                    class="text-soft-silk mt-2 text-sm hover:underline"
                    @click="searchQuery = ''"
                >
                    Clear search
                </button>
            </div>

            <!-- Grid Layout -->
            <TransitionGroup
                v-else
                name="list"
                tag="ul"
                class="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3"
            >
                <UiLibraryPromptCard
                    v-for="template in filteredTemplates"
                    :key="template.id"
                    :template="template"
                    @open-edit-modal="openEditModal"
                    @delete-template="handleDeleteTemplate"
                />
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
</style>
