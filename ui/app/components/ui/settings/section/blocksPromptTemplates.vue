<script lang="ts" setup>
import type { PromptTemplate } from '@/types/settings';

// --- Composables ---
const { success, error } = useToast();
const graphEvents = useGraphEvents();
const promptTemplateStore = usePromptTemplateStore();

// --- Local State ---
const searchQuery = ref('');
const isMarketplaceOpen = ref(false);
const dragSourceIndex = ref<number | null>(null);

// --- Computed ---
const promptTemplates = computed(() => promptTemplateStore.userTemplates);
const isDragging = computed(() => dragSourceIndex.value !== null);

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

const handleMarketplaceSelect = async (template: PromptTemplate) => {
    // Check if the template is already in our user list.
    // If the user used "Fork & Edit" in the modal, it's already added to the store/list by now.
    const isOwned = promptTemplateStore.userTemplates.some((t) => t.id === template.id);

    if (!isOwned) {
        // User clicked "Use Template" on a public template -> Fork it to library
        try {
            const newTemplate = await promptTemplateStore.forkTemplate(template);
            success('Template added to your library.');
            // Open editor to allow immediate customization
            graphEvents.emit('open-prompt-template-editor', { template: newTemplate });
        } catch (err) {
            console.error(err);
            error('Failed to add template to library.');
        }
    } else {
        // If already owned, it was likely handled by "Fork & Edit" in the modal which opens the editor internally,
        // or the user selected an existing template. We just ensure the list is fresh.
        fetchTemplates(true);
    }
};

// --- Drag & Drop Handlers ---
const onDragStart = (event: DragEvent, index: number) => {
    if (searchQuery.value) {
        event.preventDefault();
        return;
    }
    dragSourceIndex.value = index;

    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.dropEffect = 'move';
        // We can set a custom drag image here if desired, but default ghost is usually fine
    }
};

const onDragEnter = (index: number) => {
    // If we are not dragging, or if we are filtering, ignore
    if (dragSourceIndex.value === null || searchQuery.value) return;

    // If we are over the item we are currently dragging, ignore
    if (index === dragSourceIndex.value) return;

    // Perform the swap locally
    promptTemplateStore.moveTemplateLocal(dragSourceIndex.value, index);

    // Update the tracker to the new position so subsequent moves are calculated correctly
    dragSourceIndex.value = index;
};

const onDrop = () => {
    // The actual saving happens in dragEnd to cover dropping outside valid targets
    // This handler is primarily to prevent default browser behavior
};

const onDragEnd = async () => {
    if (dragSourceIndex.value !== null) {
        // Persist the new order to the backend
        await promptTemplateStore.saveOrder();
        dragSourceIndex.value = null;
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
                    >
                    or
                    <code class="bg-stone-gray/10 rounded px-1 py-0.5 font-mono text-xs"
                        >&lbrace;&lbrace;input:default&rbrace;&rbrace;</code
                    >) to standardize your workflow nodes. Reorder templates via drag-and-drop.
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

                <!-- Marketplace Button -->
                <button
                    class="hover:bg-stone-gray/10 text-stone-gray hover:text-soft-silk flex
                        flex-shrink-0 cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm
                        font-bold transition-all"
                    @click="isMarketplaceOpen = true"
                >
                    <UiIcon name="MdiWeb" class="h-4 w-4" />
                    <span class="hidden sm:inline">Marketplace</span>
                </button>

                <!-- Create Button -->
                <button
                    class="bg-ember-glow hover:bg-ember-glow/90 text-soft-silk flex flex-shrink-0
                        cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm font-bold
                        transition-all"
                    @click="openCreateModal"
                >
                    <UiIcon name="Fa6SolidPlus" class="h-4 w-4" />
                    <span class="hidden sm:inline">Create</span>
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
                <div class="mt-4 flex items-center gap-3">
                    <button
                        class="text-ember-glow hover:text-ember-glow/80 cursor-pointer text-sm
                            font-bold transition-colors"
                        @click="openCreateModal"
                    >
                        Create your first template
                    </button>
                    <span class="text-stone-gray/30 text-xs">or</span>
                    <button
                        class="text-stone-gray hover:text-soft-silk cursor-pointer text-sm font-bold
                            transition-colors"
                        @click="isMarketplaceOpen = true"
                    >
                        Browse Marketplace
                    </button>
                </div>
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
                :class="{ 'no-transition': isDragging }"
            >
                <UiLibraryPromptCard
                    v-for="(template, index) in filteredTemplates"
                    :key="template.id"
                    :template="template"
                    :draggable="!searchQuery"
                    class="cursor-grab active:cursor-grabbing"
                    :class="{
                        'border-stone-gray/40 scale-95 border-dashed opacity-40':
                            dragSourceIndex === index,
                    }"
                    @dragstart="onDragStart($event, index)"
                    @drop="onDrop"
                    @dragenter.prevent="onDragEnter(index)"
                    @dragover.prevent
                    @dragend="onDragEnd"
                    @open-edit-modal="openEditModal"
                    @delete-template="handleDeleteTemplate"
                />
            </TransitionGroup>
        </div>

        <!-- Marketplace Modal -->
        <UiLibraryPromptMarketplaceModal
            :is-open="isMarketplaceOpen"
            @close="isMarketplaceOpen = false"
            @select="handleMarketplaceSelect"
        />
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
