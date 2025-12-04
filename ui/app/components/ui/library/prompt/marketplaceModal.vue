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
const { error, success } = useToast();
const promptTemplateStore = usePromptTemplateStore();
const graphEvents = useGraphEvents();

// --- State ---
const searchQuery = ref('');
const selectedTemplate = ref<PromptTemplate | null>(null);
const isForking = ref(false);

// --- Computed ---
const templates = computed(() => promptTemplateStore.publicTemplates);
const loading = computed(() => promptTemplateStore.isLoadingPublic);
const bookmarkedIds = computed(() => promptTemplateStore.bookmarkedTemplateIds);

const filteredTemplates = computed(() => {
    if (!searchQuery.value) return templates.value;
    const query = searchQuery.value.toLowerCase();
    return templates.value.filter(
        (t) =>
            t.name.toLowerCase().includes(query) ||
            (t.description && t.description.toLowerCase().includes(query)),
    );
});

const isSelectedBookmarked = computed(() => {
    if (!selectedTemplate.value) return false;
    return bookmarkedIds.value.has(selectedTemplate.value.id);
});

const previewParts = computed(() => {
    if (!selectedTemplate.value) return [];
    const text = selectedTemplate.value.templateText;
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
        }
        const content = match[2] ? `${match[1]}:${match[2]}` : match[1];
        parts.push({ type: 'variable', content });
        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push({ type: 'text', content: text.slice(lastIndex) });
    }
    return parts;
});

const detectedVariables = computed(() => {
    if (!selectedTemplate.value) return [];
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const matches = selectedTemplate.value.templateText.matchAll(regex);
    return Array.from(new Set(Array.from(matches, (m) => m[1])));
});

// --- Methods ---
const fetchPublicTemplates = async (force = false) => {
    try {
        await Promise.all([
            promptTemplateStore.fetchPublicTemplates(force),
            promptTemplateStore.fetchBookmarkedTemplates(),
        ]);
    } catch (err) {
        console.error('Failed to load public templates:', err);
        error('Failed to load marketplace templates.');
    }
};

const handleSelect = () => {
    if (selectedTemplate.value) {
        emit('select', selectedTemplate.value);
        handleClose();
    }
};

const handleClose = () => {
    emit('close');
    setTimeout(() => {
        selectedTemplate.value = null;
        searchQuery.value = '';
    }, 300);
};

const handleToggleBookmark = async () => {
    if (!selectedTemplate.value) return;
    try {
        await promptTemplateStore.toggleBookmark(selectedTemplate.value);
    } catch {
        error('Failed to update bookmark.');
    }
};

const handleForkAndEdit = async () => {
    if (!selectedTemplate.value) return;
    isForking.value = true;
    try {
        const newTemplate = await promptTemplateStore.forkTemplate(selectedTemplate.value);
        success('Template forked successfully.');

        emit('select', newTemplate);

        handleClose();

        setTimeout(() => {
            graphEvents.emit('open-prompt-template-editor', { template: newTemplate });
        }, 100);
    } catch (err) {
        console.error('Failed to fork template:', err);
        error('Failed to fork template.');
    } finally {
        isForking.value = false;
    }
};

// --- Lifecycle ---
watch(
    () => props.isOpen,
    (isOpen) => {
        if (isOpen) {
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
                :animate="{ opacity: 1, transition: { duration: 0.2 } }"
                :exit="{ opacity: 0, transition: { duration: 0.2 } }"
                class="bg-anthracite/40 fixed inset-0 z-[25] flex items-center justify-center p-4
                    backdrop-blur-md sm:p-6 md:p-8"
                @click.self="handleClose"
            >
                <motion.div
                    :initial="{ opacity: 0, scale: 0.95, y: 10 }"
                    :animate="{
                        opacity: 1,
                        scale: 1,
                        y: 0,
                        transition: { duration: 0.3, ease: 'easeOut' },
                    }"
                    :exit="{
                        opacity: 0,
                        scale: 0.95,
                        y: 10,
                        transition: { duration: 0.2, ease: 'easeIn' },
                    }"
                    class="bg-obsidian/95 border-stone-gray/10 flex h-[85vh] w-full max-w-6xl
                        flex-col overflow-hidden rounded-2xl border shadow-2xl md:flex-row"
                >
                    <!-- LEFT SIDEBAR: List & Search -->
                    <div
                        class="border-stone-gray/10 flex w-full flex-col border-r md:w-1/3
                            lg:w-[350px]"
                    >
                        <!-- Header -->
                        <div class="border-stone-gray/10 flex-shrink-0 border-b p-5">
                            <h2 class="text-soft-silk text-lg font-bold">Template Marketplace</h2>
                            <p class="text-stone-gray/60 text-xs">
                                Discover templates from the community.
                            </p>

                            <!-- Search -->
                            <div class="relative mt-4">
                                <UiIcon
                                    name="MdiMagnify"
                                    class="text-stone-gray absolute top-1/2 left-3 h-4 w-4
                                        -translate-y-1/2 opacity-70"
                                />
                                <input
                                    v-model="searchQuery"
                                    type="text"
                                    placeholder="Search templates..."
                                    class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                        placeholder:text-stone-gray/40 focus:border-soft-silk/30
                                        block w-full rounded-lg border py-2 pr-4 pl-9 text-sm
                                        transition-colors outline-none focus:ring-0"
                                />
                            </div>
                        </div>

                        <!-- List -->
                        <div class="dark-scrollbar flex-1 overflow-y-auto p-3">
                            <div
                                v-if="loading && !templates.length"
                                class="flex h-32 flex-col items-center justify-center gap-3"
                            >
                                <span class="text-stone-gray/50 text-sm">Loading templates...</span>
                            </div>

                            <div
                                v-else-if="!filteredTemplates.length"
                                class="text-stone-gray/50 flex h-32 flex-col items-center
                                    justify-center text-center text-xs"
                            >
                                <span>No templates found.</span>
                            </div>

                            <ul v-else class="space-y-2">
                                <li
                                    v-for="template in filteredTemplates"
                                    :key="template.id"
                                    @click="selectedTemplate = template"
                                >
                                    <div
                                        class="group relative cursor-pointer rounded-xl border p-3
                                            transition-all duration-200"
                                        :class="[
                                            selectedTemplate?.id === template.id
                                                ? 'bg-ember-glow/10 border-ember-glow/50 shadow-lg'
                                                : `bg-anthracite/20 hover:bg-anthracite/40
                                                    hover:border-stone-gray/20 border-transparent`,
                                        ]"
                                    >
                                        <div class="flex items-start justify-between gap-2">
                                            <h3
                                                class="truncate text-sm font-semibold
                                                    transition-colors"
                                                :class="
                                                    selectedTemplate?.id === template.id
                                                        ? 'text-ember-glow'
                                                        : 'text-soft-silk'
                                                "
                                            >
                                                {{ template.name }}
                                            </h3>
                                            <UiIcon
                                                v-if="bookmarkedIds.has(template.id)"
                                                name="MaterialSymbolsStarRounded"
                                                class="text-ember-glow h-4 w-4 shrink-0"
                                            />
                                            <div
                                                v-else-if="selectedTemplate?.id === template.id"
                                                class="bg-ember-glow h-1.5 w-1.5 shrink-0
                                                    rounded-full
                                                    shadow-[0_0_8px_rgba(235,94,40,0.8)]"
                                            ></div>
                                        </div>
                                        <p
                                            class="text-stone-gray/60 mt-1 line-clamp-2 text-xs
                                                leading-relaxed"
                                        >
                                            {{ template.description || 'No description.' }}
                                        </p>
                                        <div
                                            class="text-stone-gray/40 mt-2 flex items-center gap-2
                                                text-[10px]"
                                        >
                                            <UiIcon name="MdiCalendarMonth" class="h-3 w-3" />
                                            <NuxtTime
                                                :datetime="template.updatedAt"
                                                locale="en-US"
                                                relative
                                            />
                                        </div>
                                    </div>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <!-- RIGHT SIDEBAR: Preview -->
                    <div class="bg-anthracite/10 relative flex flex-1 flex-col overflow-hidden">
                        <!-- Close Button (Mobile/Desktop) -->
                        <button
                            class="hover:bg-stone-gray/10 absolute top-4 right-4 z-10 flex h-8 w-8
                                items-center justify-center rounded-full transition-colors"
                            @click="handleClose"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-5 w-5" />
                        </button>

                        <!-- Empty State -->
                        <div
                            v-if="!selectedTemplate"
                            class="text-stone-gray/40 flex h-full flex-col items-center
                                justify-center text-center"
                        >
                            <div
                                class="bg-stone-gray/5 mb-4 flex h-20 w-20 items-center
                                    justify-center rounded-full"
                            >
                                <UiIcon
                                    name="MaterialSymbolsTextSnippetOutlineRounded"
                                    class="h-10 w-10 opacity-50"
                                />
                            </div>
                            <p class="text-lg font-medium">Select a template</p>
                            <p class="text-sm">Browse the list to view template details.</p>
                        </div>

                        <!-- Detail View -->
                        <div v-else class="flex h-full flex-col">
                            <!-- Preview Header -->
                            <div class="border-stone-gray/10 border-b p-6 pr-12">
                                <div class="flex items-center gap-3">
                                    <h2 class="text-soft-silk text-2xl font-bold">
                                        {{ selectedTemplate.name }}
                                    </h2>
                                    <span
                                        class="bg-slate-blue/20 text-slate-blue-dark
                                            dark:text-slate-blue-300 rounded-full px-2.5 py-0.5
                                            text-xs font-medium"
                                    >
                                        Public
                                    </span>
                                </div>
                                <p class="text-stone-gray/80 mt-2 text-sm leading-relaxed">
                                    {{ selectedTemplate.description || 'No description provided.' }}
                                </p>

                                <!-- Variables Chips -->
                                <div v-if="detectedVariables.length > 0" class="mt-4">
                                    <span
                                        class="text-stone-gray/50 mb-2 block text-xs font-bold
                                            tracking-wider uppercase"
                                    >
                                        Variables
                                    </span>
                                    <div class="flex flex-wrap gap-2">
                                        <span
                                            v-for="v in detectedVariables"
                                            :key="v"
                                            class="bg-stone-gray/10 text-soft-silk/90
                                                border-stone-gray/20 flex items-center gap-1.5
                                                rounded-md border px-2 py-1 font-mono text-xs"
                                        >
                                            <UiIcon
                                                name="MdiVariable"
                                                class="text-stone-gray/50 h-3 w-3"
                                            />
                                            {{ v }}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <!-- Code Preview -->
                            <div class="dark-scrollbar flex-1 overflow-y-auto bg-black/20 p-6">
                                <div
                                    class="bg-obsidian/50 border-stone-gray/10 relative
                                        overflow-hidden rounded-xl border shadow-inner"
                                >
                                    <div
                                        class="bg-stone-gray/5 border-stone-gray/5 flex items-center
                                            justify-between border-b px-4 py-2"
                                    >
                                        <span
                                            class="text-stone-gray/50 text-xs font-bold
                                                tracking-wider uppercase"
                                            >Template Content</span
                                        >
                                        <div class="flex gap-1.5">
                                            <div
                                                class="bg-stone-gray/20 h-2.5 w-2.5 rounded-full"
                                            ></div>
                                            <div
                                                class="bg-stone-gray/20 h-2.5 w-2.5 rounded-full"
                                            ></div>
                                        </div>
                                    </div>
                                    <div
                                        class="dark-scrollbar overflow-y-auto p-4 font-mono text-sm
                                            leading-relaxed whitespace-pre-wrap"
                                    >
                                        <template v-for="(part, idx) in previewParts" :key="idx">
                                            <span
                                                v-if="part.type === 'text'"
                                                class="text-stone-gray/80"
                                                >{{ part.content }}</span
                                            >
                                            <span
                                                v-else
                                                class="text-ember-glow bg-ember-glow/10 rounded px-1
                                                    py-0.5 font-bold"
                                                >{{ part.content }}</span
                                            >
                                        </template>
                                    </div>
                                </div>
                            </div>

                            <!-- Footer Action -->
                            <div
                                class="bg-obsidian/40 border-stone-gray/10 flex items-center
                                    justify-end gap-3 border-t p-4 backdrop-blur-sm"
                            >
                                <!-- Bookmark Button -->
                                <button
                                    class="hover:bg-stone-gray/10 mr-auto flex items-center gap-2
                                        rounded-lg px-3 py-2 text-xs font-bold transition-colors"
                                    :class="
                                        isSelectedBookmarked
                                            ? 'text-ember-glow'
                                            : 'text-stone-gray hover:text-soft-silk'
                                    "
                                    @click="handleToggleBookmark"
                                >
                                    <UiIcon
                                        :name="
                                            isSelectedBookmarked
                                                ? 'MaterialSymbolsStarRounded'
                                                : 'MaterialSymbolsStarOutlineRounded'
                                        "
                                        class="h-5 w-5"
                                    />
                                    {{ isSelectedBookmarked ? 'Bookmarked' : 'Bookmark' }}
                                </button>

                                <button
                                    class="hover:bg-stone-gray/10 text-stone-gray
                                        hover:text-soft-silk rounded-lg px-4 py-2 text-sm
                                        font-medium transition-colors"
                                    @click="selectedTemplate = null"
                                >
                                    Cancel
                                </button>

                                <!-- Fork & Edit Button -->
                                <button
                                    class="hover:bg-ember-glow/20 hover:text-ember-glow
                                        text-stone-gray border-stone-gray/20
                                        hover:border-ember-glow/50 flex items-center gap-2
                                        rounded-lg border px-4 py-2 text-sm font-bold
                                        transition-all"
                                    :disabled="isForking"
                                    @click="handleForkAndEdit"
                                >
                                    <UiIcon
                                        v-if="isForking"
                                        name="SvgSpinnersRingResize"
                                        class="h-4 w-4"
                                    />
                                    <UiIcon
                                        v-else
                                        name="MaterialSymbolsForkRightRounded"
                                        class="h-4 w-4"
                                    />
                                    Fork & Edit
                                </button>

                                <button
                                    class="bg-ember-glow hover:bg-ember-glow/80 text-soft-silk
                                        shadow-ember-glow/20 flex items-center gap-2 rounded-lg px-6
                                        py-2 text-sm font-bold shadow-lg transition-all
                                        hover:scale-[1.02] active:scale-[0.98]"
                                    @click="handleSelect"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsCheckSmallRounded"
                                        class="h-5 w-5"
                                    />
                                    Use Template
                                </button>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>
