<script setup lang="ts">
import type { PromptTemplate } from '@/types/settings';

const props = defineProps<{
    templates: PromptTemplate[];
    selectedTemplateId: string | null;
}>();

const emit = defineEmits<{
    (e: 'select', template: PromptTemplate): void;
}>();

const selectedTemplate = computed(() => {
    return props.templates.find((t) => t.id === props.selectedTemplateId);
});

const internalSelected = ref<PromptTemplate | undefined>(selectedTemplate.value);

watch(internalSelected, (newTemplate) => {
    if (newTemplate && newTemplate.id !== props.selectedTemplateId) {
        emit('select', newTemplate);
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
            class="hover:bg-stone-gray/20 bg-stone-gray/10 text-soft-silk nodrag nowheel relative
                flex h-7 cursor-pointer items-center gap-1.5 rounded-lg py-2 pr-8 pl-2 text-left
                text-xs font-semibold transition-colors"
            :class="{
                'w-full min-w-[120px]': selectedTemplate?.name,
                'w-16': selectedTemplate,
            }"
        >
            <UiIcon name="MaterialSymbolsTextSnippetOutlineRounded" class="h-4 w-4 flex-shrink-0" />
            <span v-if="selectedTemplate?.name" class="block truncate">
                {{ selectedTemplate?.name }}
            </span>
            <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <UiIcon
                    name="FlowbiteChevronDownOutline"
                    class="text-soft-silk/80 h-4 w-4"
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
                class="bg-obsidian/80 border-stone-gray/20 custom_scroll absolute right-0 z-10 mt-2
                    max-h-60 w-64 origin-top-right overflow-auto rounded-md border py-1 text-base
                    shadow-lg backdrop-blur-md focus:outline-none sm:text-sm"
            >
                <div
                    v-if="!templates.length"
                    class="text-stone-gray/60 relative cursor-default px-4 py-2 select-none"
                >
                    No templates found.
                </div>
                <HeadlessListboxOption
                    v-for="template in templates"
                    :key="template.id"
                    v-slot="{ active, selected }"
                    :value="template"
                    as="template"
                >
                    <li
                        :class="[
                            active ? 'bg-ember-glow/20 text-ember-glow' : 'text-soft-silk',
                            'relative cursor-pointer py-2 pr-4 pl-10 select-none',
                        ]"
                    >
                        <div class="flex flex-col">
                            <span
                                :class="[
                                    selected ? 'font-medium' : 'font-normal',
                                    'block truncate',
                                ]"
                            >
                                {{ template.name }}
                            </span>
                            <span
                                v-if="template.description"
                                :class="[
                                    'block truncate text-xs',
                                    active ? 'text-ember-glow/70' : 'text-stone-gray',
                                ]"
                            >
                                {{ template.description }}
                            </span>
                        </div>
                        <span
                            v-if="selected"
                            class="text-ember-glow absolute inset-y-0 left-0 flex items-center pl-3"
                        >
                            <UiIcon
                                name="MaterialSymbolsCheckSmallRounded"
                                class="h-5 w-5"
                                aria-hidden="true"
                            />
                        </span>
                    </li>
                </HeadlessListboxOption>
            </HeadlessListboxOptions>
        </transition>
    </HeadlessListbox>
</template>
