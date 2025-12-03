<script lang="ts" setup>
import { motion } from 'motion-v';
import type { PromptTemplate } from '@/types/settings';

const props = defineProps<{
    isOpen: boolean;
}>();

const emit = defineEmits<{
    (e: 'close'): void;
    (e: 'select', template: PromptTemplate): void;
}>();

// --- Composables ---
const { error } = useToast();
const promptTemplateStore = usePromptTemplateStore();

// --- State ---
const searchQuery = ref('');

// --- Computed ---
const templates = computed(() => promptTemplateStore.publicTemplates);
const loading = computed(() => promptTemplateStore.isLoadingPublic);

const filteredTemplates = computed(() => {
    if (!searchQuery.value) return templates.value;
    const query = searchQuery.value.toLowerCase();
    return templates.value.filter(
        (t) =>
            t.name.toLowerCase().includes(query) ||
            (t.description && t.description.toLowerCase().includes(query)),
    );
});

// --- Methods ---
const fetchPublicTemplates = async (force = false) => {
    try {
        await promptTemplateStore.fetchPublicTemplates(force);
    } catch (err) {
        console.error('Failed to load public templates:', err);
        error('Failed to load marketplace templates.');
    }
};

const handleSelect = (template: PromptTemplate) => {
    emit('select', template);
    emit('close');
};

// --- Lifecycle ---
watch(
    () => props.isOpen,
    (isOpen) => {
        if (isOpen) {
            // Fetch in background (force refresh to get latest)
            fetchPublicTemplates(true);
        }
    },
);
</script>

<template>
    <Teleport to="body">
        <AnimatePresence>
            <motion.div
                v-if="isOpen"
                key="marketplace-modal"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1, transition: { duration: 0.3, ease: 'easeOut' } }"
                :exit="{ opacity: 0, transition: { duration: 0.2, ease: 'easeIn' } }"
                class="bg-anthracite/25 fixed inset-0 z-[25] flex items-center justify-center p-4
                    backdrop-blur-lg sm:p-6 md:p-8"
                @click.self="$emit('close')"
            >
                <motion.div
                    :initial="{ opacity: 0, scale: 0.95 }"
                    :animate="{
                        opacity: 1,
                        scale: 1,
                        transition: { duration: 0.3, ease: 'easeOut' },
                    }"
                    :exit="{
                        opacity: 0,
                        scale: 0.95,
                        transition: { duration: 0.2, ease: 'easeIn' },
                    }"
                    class="bg-obsidian/50 border-stone-gray/10 flex h-full max-h-[80vh] w-full
                        max-w-4xl flex-col overflow-hidden rounded-2xl border shadow-2xl"
                >
                    <!-- Header -->
                    <div
                        class="border-stone-gray/10 flex flex-shrink-0 items-center justify-between
                            border-b p-6"
                    >
                        <div>
                            <h2 class="text-soft-silk text-xl font-bold">Template Marketplace</h2>
                            <p class="text-stone-gray/60 text-sm">
                                Browse and use templates from the community.
                            </p>
                        </div>
                        <button
                            class="hover:bg-stone-gray/10 flex h-10 w-10 items-center justify-center
                                rounded-full transition-colors"
                            aria-label="Close"
                            @click="$emit('close')"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
                        </button>
                    </div>

                    <!-- Search -->
                    <div class="border-stone-gray/10 flex-shrink-0 border-b bg-black/10 px-6 py-4">
                        <div class="relative">
                            <UiIcon
                                name="MdiMagnify"
                                class="text-stone-gray absolute top-1/2 left-3 h-5 w-5
                                    -translate-y-1/2"
                            />
                            <input
                                v-model="searchQuery"
                                type="text"
                                placeholder="Search public templates..."
                                class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                    placeholder:text-stone-gray/50 focus:border-soft-silk/30 block
                                    w-full rounded-lg border-2 py-2.5 pr-4 pl-10 text-sm
                                    outline-none focus:ring-0"
                            />
                        </div>
                    </div>

                    <!-- Content -->
                    <div class="custom_scroll flex-1 overflow-y-auto p-6">
                        <div
                            v-if="loading && !templates.length"
                            class="flex h-40 flex-col items-center justify-center gap-3"
                        >
                            <UiIcon
                                name="SvgSpinners180Ring"
                                class="text-ember-glow h-8 w-8 animate-spin"
                            />
                            <span class="text-stone-gray text-sm">Loading templates...</span>
                        </div>

                        <div
                            v-else-if="!filteredTemplates.length"
                            class="text-stone-gray/60 flex h-40 flex-col items-center justify-center
                                text-center"
                        >
                            <UiIcon
                                name="MaterialSymbolsSearchOffRounded"
                                class="mb-2 h-10 w-10 opacity-50"
                            />
                            <p>No templates found matching your search.</p>
                        </div>

                        <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <div
                                v-for="template in filteredTemplates"
                                :key="template.id"
                                class="bg-anthracite/30 border-stone-gray/10
                                    hover:border-stone-gray/30 group flex flex-col rounded-xl border
                                    p-4 transition-all duration-200"
                            >
                                <div class="mb-2 flex items-start justify-between gap-2">
                                    <h3 class="text-soft-silk font-semibold">
                                        {{ template.name }}
                                    </h3>
                                </div>
                                <p
                                    class="text-stone-gray/70 mb-4 line-clamp-2 flex-1 text-sm
                                        leading-relaxed"
                                >
                                    {{ template.description || 'No description.' }}
                                </p>
                                <div class="mt-auto flex items-center justify-between pt-2">
                                    <div class="text-stone-gray/50 text-xs">
                                        <NuxtTime
                                            :datetime="template.updatedAt"
                                            locale="en-US"
                                            relative
                                        />
                                    </div>
                                    <button
                                        class="bg-ember-glow/10 hover:bg-ember-glow text-ember-glow
                                            hover:text-soft-silk flex items-center gap-2 rounded-lg
                                            px-3 py-1.5 text-xs font-bold transition-all
                                            duration-200"
                                        @click="handleSelect(template)"
                                    >
                                        <UiIcon
                                            name="MaterialSymbolsCheckSmallRounded"
                                            class="h-4 w-4"
                                        />
                                        Select
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>
