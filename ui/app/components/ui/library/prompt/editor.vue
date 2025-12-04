<script lang="ts" setup>
import { motion } from 'motion-v';
import type { PromptTemplate } from '@/types/settings';

// --- Composables ---
const graphEvents = useGraphEvents();
const { success, error } = useToast();
const promptTemplateStore = usePromptTemplateStore();

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

// Parses text for the live preview (highlighting variables)
const previewParts = computed(() => {
    const text = currentTemplate.value.templateText || '';
    if (!text) return [];

    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
        }
        parts.push({ type: 'variable', content: match[1] });
        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push({ type: 'text', content: text.slice(lastIndex) });
    }
    return parts;
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
            await promptTemplateStore.updateTemplate(currentTemplate.value.id!, {
                name: currentTemplate.value.name,
                description: currentTemplate.value.description,
                templateText: currentTemplate.value.templateText,
                isPublic: currentTemplate.value.isPublic,
            });
            success('Template updated successfully.');
        } else {
            await promptTemplateStore.createTemplate({
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
    <Teleport to="body">
        <AnimatePresence>
            <motion.div
                v-if="isOpen"
                key="prompt-template-editor"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1, transition: { duration: 0.2 } }"
                :exit="{ opacity: 0, transition: { duration: 0.2 } }"
                class="bg-anthracite/40 fixed inset-0 z-[30] flex items-center justify-center p-4
                    backdrop-blur-md sm:p-6 md:p-8"
                @click.self="closeEditor"
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
                    class="bg-obsidian/95 border-stone-gray/10 grid h-[85vh] w-full max-w-6xl
                        grid-rows-[auto_1fr_auto] overflow-hidden rounded-2xl border shadow-2xl"
                >
                    <!-- Header -->
                    <div
                        class="border-stone-gray/10 flex shrink-0 items-center justify-between
                            border-b px-6 py-4"
                    >
                        <h2 class="text-soft-silk text-lg font-bold">
                            {{ isEditing ? 'Edit' : 'Create' }} Prompt Template
                        </h2>
                        <button
                            class="hover:bg-stone-gray/10 flex h-8 w-8 items-center justify-center
                                rounded-full transition-colors"
                            aria-label="Close editor"
                            @click="closeEditor"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-5 w-5" />
                        </button>
                    </div>

                    <!-- Main Content Grid -->
                    <div class="grid min-h-0 grid-cols-1 lg:grid-cols-2">
                        <!-- Left Panel: Editor -->
                        <div
                            class="custom_scroll lg:border-r-stone-gray/10 flex h-full flex-col
                                gap-6 overflow-y-auto p-6 lg:border-r"
                        >
                            <!-- Name Input (Document Title Style) -->
                            <div class="group">
                                <label
                                    class="text-stone-gray/50 mb-1 block text-xs font-bold
                                        tracking-wider uppercase"
                                >
                                    Template Name
                                </label>
                                <input
                                    v-model="currentTemplate.name"
                                    type="text"
                                    placeholder="Untitled Template"
                                    class="text-soft-silk placeholder:text-stone-gray/30 w-full
                                        bg-transparent py-1 text-3xl font-bold transition-colors
                                        outline-none"
                                    required
                                    autofocus
                                />
                            </div>

                            <!-- Description -->
                            <div>
                                <label
                                    class="text-stone-gray/50 mb-2 block text-xs font-bold
                                        tracking-wider uppercase"
                                >
                                    Description
                                </label>
                                <textarea
                                    v-model="currentTemplate.description"
                                    rows="2"
                                    placeholder="Describe what this prompt does..."
                                    class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                        placeholder:text-stone-gray/40 focus:border-soft-silk/30
                                        block w-full resize-none rounded-lg border p-3 text-sm
                                        transition-colors outline-none focus:ring-0"
                                ></textarea>
                            </div>

                            <!-- Template Editor -->
                            <div class="flex flex-1 flex-col">
                                <div class="mb-2 flex items-center justify-between">
                                    <label
                                        class="text-stone-gray/50 flex items-center gap-2 text-xs
                                            font-bold tracking-wider uppercase"
                                    >
                                        Prompt Content
                                        <UiSettingsInfobubble direction="left">
                                            <p class="font-semibold">Variables</p>
                                            <p class="mt-1 text-sm">
                                                Wrap text in double curly braces to create
                                                variables:
                                                <code
                                                    class="bg-obsidian/50 rounded px-1 py-0.5
                                                        font-mono text-xs"
                                                    >&lbrace;&lbrace;variable&rbrace;&rbrace;</code
                                                >.
                                            </p>
                                        </UiSettingsInfobubble>
                                    </label>
                                </div>
                                <div class="relative flex-1">
                                    <textarea
                                        v-model="currentTemplate.templateText"
                                        placeholder="Write your prompt here. Use {{variable}} to insert dynamic inputs."
                                        class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                            placeholder:text-stone-gray/30 focus:border-soft-silk/30
                                            custom_scroll absolute inset-0 h-full w-full resize-none
                                            rounded-lg border p-4 font-mono text-sm leading-relaxed
                                            transition-colors outline-none focus:ring-0"
                                        required
                                    ></textarea>
                                </div>
                            </div>
                        </div>

                        <!-- Right Panel: Preview & Config -->
                        <div
                            class="bg-anthracite/5 custom_scroll flex h-full flex-col
                                overflow-y-auto p-6"
                        >
                            <!-- Settings Section -->
                            <div
                                class="border-stone-gray/10 bg-anthracite/20 mb-6 rounded-xl border
                                    p-4"
                            >
                                <div class="flex items-center justify-between">
                                    <div class="flex flex-col">
                                        <span class="text-soft-silk text-sm font-semibold"
                                            >Public Template</span
                                        >
                                        <span class="text-stone-gray/60 text-xs"
                                            >Allow others to discover this template.</span
                                        >
                                    </div>
                                    <HeadlessSwitch
                                        v-model="currentTemplate.isPublic"
                                        :class="
                                            currentTemplate.isPublic
                                                ? 'bg-ember-glow'
                                                : 'bg-stone-gray/20'
                                        "
                                        class="relative inline-flex h-6 w-11 items-center
                                            rounded-full transition-colors focus:outline-none"
                                    >
                                        <span
                                            :class="
                                                currentTemplate.isPublic
                                                    ? 'translate-x-6'
                                                    : 'translate-x-1'
                                            "
                                            class="inline-block h-4 w-4 transform rounded-full
                                                bg-white transition-transform"
                                        />
                                    </HeadlessSwitch>
                                </div>
                            </div>

                            <!-- Live Preview Section -->
                            <div class="flex flex-1 flex-col">
                                <div class="mb-3 flex items-center justify-between">
                                    <label
                                        class="text-stone-gray/50 text-xs font-bold tracking-wider
                                            uppercase"
                                    >
                                        Live Preview
                                    </label>
                                    <span
                                        v-if="detectedVariables.length"
                                        class="bg-slate-blue/20 text-slate-blue-dark
                                            dark:text-slate-blue-300 rounded-full px-2 py-0.5
                                            text-[10px] font-bold"
                                    >
                                        {{ detectedVariables.length }} Variable{{
                                            detectedVariables.length !== 1 ? 's' : ''
                                        }}
                                    </span>
                                </div>

                                <!-- Variable Chips Summary -->
                                <div v-if="detectedVariables.length > 0" class="mb-4">
                                    <div class="flex flex-wrap gap-2">
                                        <span
                                            v-for="v in detectedVariables"
                                            :key="v"
                                            class="bg-stone-gray/10 text-stone-gray
                                                border-stone-gray/10 flex items-center gap-1.5
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

                                <div
                                    class="bg-obsidian/50 border-stone-gray/10 custom_scroll flex-1
                                        overflow-y-auto rounded-xl border p-4 shadow-inner"
                                >
                                    <div
                                        v-if="!currentTemplate.templateText"
                                        class="text-stone-gray/30 flex h-full items-center
                                            justify-center text-sm italic"
                                    >
                                        Start typing to see preview...
                                    </div>
                                    <div
                                        v-else
                                        class="text-soft-silk/80 font-mono text-sm leading-relaxed
                                            whitespace-pre-wrap"
                                    >
                                        <template v-for="(part, idx) in previewParts" :key="idx">
                                            <span v-if="part.type === 'text'">{{
                                                part.content
                                            }}</span>
                                            <span
                                                v-else
                                                class="text-ember-glow bg-ember-glow/10 rounded px-1
                                                    py-0.5 font-bold"
                                            >
                                                {{ part.content }}
                                            </span>
                                        </template>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div
                        class="bg-anthracite/20 border-stone-gray/10 flex shrink-0 items-center
                            justify-end gap-3 border-t px-6 py-4"
                    >
                        <button
                            type="button"
                            class="hover:bg-stone-gray/10 text-stone-gray hover:text-soft-silk
                                rounded-lg px-4 py-2 text-sm font-medium transition-colors"
                            @click="closeEditor"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            class="bg-ember-glow hover:bg-ember-glow/90 text-soft-silk
                                shadow-ember-glow/20 flex items-center gap-2 rounded-lg px-6 py-2
                                text-sm font-bold shadow-lg transition-all hover:scale-[1.02]
                                active:scale-[0.98]"
                            @click="handleSave"
                        >
                            <UiIcon name="MdiContentSaveOutline" class="h-4 w-4" />
                            {{ isEditing ? 'Save Changes' : 'Create Template' }}
                        </button>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>
