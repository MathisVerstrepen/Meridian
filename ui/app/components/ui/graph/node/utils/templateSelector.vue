<script setup lang="ts">
import type { PromptTemplate } from '@/types/settings';

const props = defineProps<{
    templates: PromptTemplate[];
    selectedTemplateId: string | null;
}>();

const emit = defineEmits<{
    (e: 'select', template: PromptTemplate): void;
}>();

// --- Store ---
const promptTemplateStore = usePromptTemplateStore();
const bookmarkedIds = computed(() => promptTemplateStore.bookmarkedTemplateIds);

// --- State ---
const query = ref('');
const isMarketplaceOpen = ref(false);

// --- Computed ---
const selectedTemplate = computed(() => {
    return props.templates.find((t) => t.id === props.selectedTemplateId);
});

const filteredTemplates = computed(() => {
    if (query.value === '') {
        // Sort: Bookmarked first, then others
        return [...props.templates].sort((a, b) => {
            const aB = bookmarkedIds.value.has(a.id);
            const bB = bookmarkedIds.value.has(b.id);
            if (aB && !bB) return -1;
            if (!aB && bB) return 1;
            return a.name.localeCompare(b.name);
        });
    }
    const lowerQuery = query.value.toLowerCase();
    const filtered = props.templates.filter((t) => {
        return (
            t.name.toLowerCase().includes(lowerQuery) ||
            (t.description && t.description.toLowerCase().includes(lowerQuery))
        );
    });
    // Sort filtered results: Bookmarked first
    return filtered.sort((a, b) => {
        const aB = bookmarkedIds.value.has(a.id);
        const bB = bookmarkedIds.value.has(b.id);
        if (aB && !bB) return -1;
        if (!aB && bB) return 1;
        return a.name.localeCompare(b.name);
    });
});

// --- Methods ---
const handleSelect = (template: PromptTemplate) => {
    if (template) {
        emit('select', template);
    }
};

const handleMarketplaceSelect = (template: PromptTemplate) => {
    emit('select', template);
};

// Ensure the query is reset when the selection changes externally
watch(
    () => props.selectedTemplateId,
    () => {
        query.value = '';
    },
);
</script>

<template>
    <div class="relative w-full max-w-[300px] min-w-[200px]">
        <HeadlessCombobox
            :model-value="selectedTemplate"
            nullable
            @update:model-value="handleSelect"
        >
            <div class="relative">
                <!-- Trigger / Input -->
                <div
                    class="bg-stone-gray/5 border-stone-gray/20 hover:border-stone-gray/20 relative
                        w-full cursor-text overflow-hidden rounded-lg border text-left
                        transition-colors duration-200 sm:text-sm"
                >
                    <HeadlessComboboxInput
                        class="text-soft-silk placeholder:text-stone-gray/80 w-full border-none
                            bg-transparent py-1 pr-10 pl-3 text-xs leading-5 focus:ring-0
                            focus:outline-0"
                        :display-value="(t: any) => t?.name"
                        placeholder="Select or search template..."
                        @change="query = $event.target.value"
                    />
                    <HeadlessComboboxButton
                        class="hover:bg-stone-gray/5 absolute inset-y-0 right-0 flex cursor-pointer
                            items-center rounded-lg px-1.5 transition-colors"
                    >
                        <UiIcon
                            name="FlowbiteChevronDownOutline"
                            class="text-stone-gray/80 h-5 w-5"
                            aria-hidden="true"
                        />
                    </HeadlessComboboxButton>
                </div>

                <!-- Dropdown Options -->
                <transition
                    leave-active-class="transition ease-in duration-100"
                    leave-from-class="opacity-100"
                    leave-to-class="opacity-0"
                    after-leave="query = ''"
                >
                    <HeadlessComboboxOptions
                        class="bg-obsidian/90 border-stone-gray/20 absolute z-50 mt-1 max-h-80
                            w-full overflow-hidden rounded-xl border py-1 text-base shadow-2xl
                            backdrop-blur-xl focus:outline-none sm:text-sm"
                    >
                        <!-- Empty State (Local) -->
                        <div
                            v-if="filteredTemplates.length === 0 && query !== ''"
                            class="text-stone-gray/60 relative cursor-default px-4 py-3 text-center
                                text-xs select-none"
                        >
                            No templates found.
                        </div>

                        <!-- Template Options -->
                        <div v-else class="nodrag nowheel dark-scrollbar max-h-60 overflow-y-auto">
                            <HeadlessComboboxOption
                                v-for="template in filteredTemplates"
                                :key="template.id"
                                v-slot="{ selected, active }"
                                as="template"
                                :value="template"
                            >
                                <li
                                    class="relative cursor-pointer py-2 pr-4 pl-3 transition-colors
                                        select-none"
                                    :class="{
                                        'bg-ember-glow/10 text-soft-silk': active,
                                        'text-stone-gray': !active,
                                    }"
                                >
                                    <div class="flex items-center justify-between gap-2">
                                        <div class="flex min-w-0 flex-col">
                                            <div class="flex items-center gap-1.5">
                                                <span
                                                    class="truncate text-xs font-medium"
                                                    :class="{
                                                        'text-ember-glow': selected,
                                                        'text-soft-silk': active && !selected,
                                                    }"
                                                >
                                                    {{ template.name }}
                                                </span>
                                                <!-- Bookmark Icon -->
                                                <UiIcon
                                                    v-if="bookmarkedIds.has(template.id)"
                                                    name="MaterialSymbolsStarRounded"
                                                    class="text-ember-glow h-3 w-3"
                                                    title="Bookmarked"
                                                />
                                            </div>
                                            <span
                                                v-if="template.description"
                                                class="truncate text-[10px] opacity-60"
                                            >
                                                {{ template.description }}
                                            </span>
                                        </div>
                                        <span
                                            v-if="selected"
                                            class="text-ember-glow flex items-center pl-1"
                                        >
                                            <UiIcon
                                                name="MaterialSymbolsCheckSmallRounded"
                                                class="h-4 w-4"
                                                aria-hidden="true"
                                            />
                                        </span>
                                    </div>
                                </li>
                            </HeadlessComboboxOption>
                        </div>

                        <!-- Divider -->
                        <div class="border-stone-gray/10 my-1 border-t"></div>

                        <!-- Marketplace Button (Sticky Bottom feel) -->
                        <div class="px-1 py-1">
                            <button
                                class="group flex w-full items-center justify-between rounded-lg
                                    px-2 py-1.5 text-xs transition-colors"
                                :class="[
                                    filteredTemplates.length === 0
                                        ? 'bg-ember-glow text-soft-silk'
                                        : `hover:bg-stone-gray/10 text-stone-gray
                                            hover:text-soft-silk`,
                                ]"
                                @click.prevent="isMarketplaceOpen = true"
                            >
                                <div class="flex items-center gap-2">
                                    <UiIcon name="MdiWeb" class="h-3.5 w-3.5" />
                                    <span class="font-medium">Browse Marketplace</span>
                                </div>
                                <UiIcon
                                    name="MdiArrowUp"
                                    class="h-4 w-4 rotate-[45deg] opacity-0 transition-opacity
                                        group-hover:opacity-100"
                                    :class="{ 'opacity-100': filteredTemplates.length === 0 }"
                                />
                            </button>
                        </div>
                    </HeadlessComboboxOptions>
                </transition>
            </div>
        </HeadlessCombobox>

        <!-- Marketplace Modal -->
        <UiLibraryPromptMarketplaceModal
            :is-open="isMarketplaceOpen"
            @close="isMarketplaceOpen = false"
            @select="handleMarketplaceSelect"
        />
    </div>
</template>
