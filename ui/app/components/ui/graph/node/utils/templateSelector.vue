<script setup lang="ts">
import type { PromptTemplate } from '@/types/settings';

const props = defineProps<{
    templates: PromptTemplate[];
    selectedTemplateId: string | null;
}>();

const emit = defineEmits<{
    (e: 'select', template: PromptTemplate): void;
}>();

// --- State ---
const searchQuery = ref('');
const internalSelected = ref<PromptTemplate | undefined>();

// --- Computed ---
const selectedTemplate = computed(() => {
    return props.templates.find((t) => t.id === props.selectedTemplateId);
});

const filteredTemplates = computed(() => {
    if (!searchQuery.value) return props.templates;
    const query = searchQuery.value.toLowerCase();
    return props.templates.filter(
        (t) =>
            t.name.toLowerCase().includes(query) ||
            (t.description && t.description.toLowerCase().includes(query)),
    );
});

// --- Watchers ---
watch(internalSelected, (newTemplate) => {
    if (newTemplate && newTemplate.id !== props.selectedTemplateId) {
        emit('select', newTemplate);
        searchQuery.value = '';
    }
});

watch(
    () => props.selectedTemplateId,
    (newId) => {
        internalSelected.value = props.templates.find((t) => t.id === newId);
    },
    { immediate: true },
);
</script>

<template>
    <HeadlessListbox v-model="internalSelected" as="div" class="relative">
        <HeadlessListboxButton
            class="hover:bg-stone-gray/20 bg-stone-gray/10 text-soft-silk nodrag nowheel
                hover:border-stone-gray/30 relative flex h-7 cursor-pointer items-center gap-2
                rounded-lg border border-transparent py-1 pr-8 pl-2 text-left text-xs font-semibold
                transition-all duration-200 focus:outline-none"
            :class="{
                'w-full min-w-[140px]': selectedTemplate?.name,
                'w-auto': !selectedTemplate,
            }"
        >
            <UiIcon
                name="MaterialSymbolsTextSnippetOutlineRounded"
                class="text-soft-silk/80 h-4 w-4 flex-shrink-0"
            />
            <span v-if="selectedTemplate?.name" class="block truncate">
                {{ selectedTemplate?.name }}
            </span>
            <span v-else class="text-soft-silk/80">Template</span>
            <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <UiIcon
                    name="FlowbiteChevronDownOutline"
                    class="text-soft-silk/60 h-4 w-4"
                    aria-hidden="true"
                />
            </span>
        </HeadlessListboxButton>

        <transition
            leave-active-class="transition duration-100 ease-in"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <HeadlessListboxOptions
                class="bg-obsidian/90 border-stone-gray/20 custom_scroll absolute right-0 z-50 mt-2
                    max-h-80 w-72 origin-top-right overflow-hidden rounded-xl border py-1 text-base
                    shadow-2xl backdrop-blur-xl focus:outline-none sm:text-sm"
            >
                <!-- Search Header -->
                <div class="border-stone-gray/10 sticky top-0 z-10 border-b px-2 py-2">
                    <div class="bg-stone-gray/20 flex items-center rounded-lg px-2">
                        <UiIcon name="MdiMagnify" class="text-stone-gray h-4 w-4" />
                        <input
                            v-model="searchQuery"
                            type="text"
                            class="text-soft-silk placeholder:text-stone-gray/60 w-full
                                bg-transparent px-2 py-1.5 text-xs focus:outline-none"
                            placeholder="Search templates..."
                            @keydown.stop
                        />
                    </div>
                </div>

                <!-- Empty State -->
                <div
                    v-if="!filteredTemplates.length"
                    class="text-stone-gray/60 flex flex-col items-center justify-center px-4 py-6
                        text-center text-xs"
                >
                    <UiIcon
                        name="MaterialSymbolsSearchOffRounded"
                        class="mb-1 h-8 w-8 opacity-50"
                    />
                    <span>No templates found.</span>
                </div>

                <!-- Options List -->
                <div class="custom_scroll max-h-60 overflow-y-auto py-1">
                    <HeadlessListboxOption
                        v-for="template in filteredTemplates"
                        :key="template.id"
                        v-slot="{ active, selected }"
                        :value="template"
                        as="template"
                    >
                        <li
                            :class="[
                                active ? 'bg-ember-glow/10' : '',
                                'relative cursor-pointer px-3 py-2.5 transition-colors select-none',
                            ]"
                        >
                            <div class="flex items-start gap-3">
                                <div
                                    class="bg-stone-gray/10 mt-0.5 flex h-5 w-5 flex-shrink-0
                                        items-center justify-center rounded"
                                >
                                    <UiIcon
                                        v-if="selected"
                                        name="MaterialSymbolsCheckSmallRounded"
                                        class="text-ember-glow h-5 w-5"
                                    />
                                    <UiIcon
                                        v-else
                                        name="MaterialSymbolsTextSnippetOutlineRounded"
                                        class="text-stone-gray/50 h-3.5 w-3.5"
                                    />
                                </div>
                                <span
                                    :class="[
                                        selected
                                            ? 'text-ember-glow font-medium'
                                            : 'text-soft-silk font-normal',
                                        'block truncate pt-0.5 text-sm',
                                    ]"
                                >
                                    {{ template.name }}
                                </span>
                            </div>
                        </li>
                    </HeadlessListboxOption>
                </div>
            </HeadlessListboxOptions>
        </transition>
    </HeadlessListbox>
</template>
