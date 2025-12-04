<script lang="ts" setup>
import type { PromptTemplate } from '@/types/settings';

const props = defineProps<{
    template: PromptTemplate;
}>();

defineEmits<{
    (e: 'open-edit-modal', template: PromptTemplate): void;
    (e: 'delete-template', templateId: string): void;
}>();

const detectedVariables = computed(() => {
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const matches = props.template.templateText.matchAll(regex);
    const variables = new Set(Array.from(matches, (m) => m[1]));
    return Array.from(variables);
});

const displayedVariables = computed(() => {
    return detectedVariables.value.slice(0, 3);
});

const remainingVariablesCount = computed(() => {
    return Math.max(0, detectedVariables.value.length - 3);
});
</script>

<template>
    <li
        class="group bg-anthracite/20 border-stone-gray/10 hover:border-stone-gray/30 relative flex
            h-full flex-col rounded-2xl border transition-all duration-300 hover:-translate-y-0.5
            hover:shadow-xl"
    >
        <!-- Main Clickable Area -->
        <div
            class="flex flex-1 cursor-pointer flex-col p-5"
            @click="$emit('open-edit-modal', template)"
        >
            <!-- Header -->
            <div class="flex items-start justify-between gap-3">
                <div class="flex items-center gap-3">
                    <div
                        class="bg-stone-gray/5 group-hover:bg-ember-glow/10 border-stone-gray/10
                            group-hover:border-ember-glow/20 flex h-10 w-10 flex-shrink-0
                            items-center justify-center rounded-xl border transition-colors
                            duration-300"
                    >
                        <UiIcon
                            name="MaterialSymbolsTextSnippetOutlineRounded"
                            class="text-stone-gray group-hover:text-ember-glow h-5 w-5
                                transition-colors duration-300"
                        />
                    </div>
                    <div>
                        <h4
                            class="text-soft-silk group-hover:text-ember-glow text-base
                                leading-tight font-bold transition-colors duration-200"
                        >
                            {{ template.name }}
                        </h4>
                        <div class="mt-0.5 flex flex-wrap items-center gap-2">
                            <div
                                v-if="template.isPublic"
                                class="text-stone-gray/60 flex items-center gap-1 text-[10px]
                                    font-medium tracking-wider uppercase"
                            >
                                <UiIcon name="MdiWeb" class="h-3 w-3" />
                                Public
                            </div>
                            <div
                                v-if="template.username"
                                class="text-stone-gray/50 text-[10px] font-medium"
                            >
                                by {{ template.username }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Description -->
            <p
                class="text-stone-gray/70 group-hover:text-stone-gray/90 mt-4 line-clamp-2
                    min-h-[2.5em] text-sm leading-relaxed transition-colors"
            >
                {{ template.description || 'No description provided.' }}
            </p>

            <!-- Variables Preview -->
            <div class="mt-4 flex flex-wrap items-center gap-2">
                <div
                    v-if="detectedVariables.length === 0"
                    class="text-stone-gray/40 text-xs italic"
                >
                    No variables defined
                </div>
                <template v-else>
                    <span
                        v-for="variable in displayedVariables"
                        :key="variable"
                        class="bg-stone-gray/10 text-stone-gray border-stone-gray/10 rounded-md
                            border px-1.5 py-0.5 font-mono text-[10px] font-medium"
                    >
                        {{ variable }}
                    </span>
                    <span
                        v-if="remainingVariablesCount > 0"
                        class="text-stone-gray/50 text-[10px] font-medium"
                    >
                        +{{ remainingVariablesCount }} more
                    </span>
                </template>
            </div>
        </div>

        <!-- Footer / Divider -->
        <div class="border-stone-gray/10 mx-5 border-t"></div>

        <!-- Footer Actions -->
        <div class="flex items-center justify-between p-3 px-5">
            <span class="text-stone-gray/40 flex items-center gap-1.5 text-xs font-medium">
                <UiIcon name="MdiCalendarMonth" class="h-3.5 w-3.5" />
                <NuxtTime :datetime="template.updatedAt" locale="en-US" relative />
            </span>

            <!-- Context Menu -->
            <HeadlessMenu as="div" class="relative inline-block text-left">
                <div>
                    <HeadlessMenuButton
                        class="hover:bg-stone-gray/10 text-stone-gray hover:text-soft-silk flex h-8
                            w-8 items-center justify-center rounded-full transition-colors"
                        @click.stop
                    >
                        <UiIcon name="Fa6SolidEllipsisVertical" class="h-3.5 w-3.5" />
                    </HeadlessMenuButton>
                </div>
                <transition
                    enter-active-class="transition ease-out duration-100"
                    enter-from-class="transform opacity-0 scale-95"
                    enter-to-class="transform opacity-100 scale-100"
                    leave-active-class="transition ease-in duration-75"
                    leave-from-class="transform opacity-100 scale-100"
                    leave-to-class="transform opacity-0 scale-95"
                >
                    <HeadlessMenuItems
                        class="bg-obsidian border-stone-gray/10 divide-stone-gray/10 absolute
                            right-0 bottom-full mb-2 w-36 origin-bottom-right divide-y rounded-xl
                            border shadow-xl backdrop-blur-2xl focus:outline-none"
                    >
                        <div class="p-1">
                            <HeadlessMenuItem v-slot="{ active }">
                                <button
                                    :class="[
                                        active
                                            ? 'bg-stone-gray/10 text-soft-silk'
                                            : 'text-stone-gray',
                                        `group flex w-full items-center rounded-lg px-3 py-2 text-xs
                                        font-medium transition-colors`,
                                    ]"
                                    @click="$emit('open-edit-modal', template)"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsEditRounded"
                                        class="mr-2 h-4 w-4 opacity-70"
                                    />
                                    Edit
                                </button>
                            </HeadlessMenuItem>
                        </div>
                        <div class="p-1">
                            <HeadlessMenuItem v-slot="{ active }">
                                <button
                                    :class="[
                                        active ? 'bg-red-500/10 text-red-400' : 'text-red-400/80',
                                        `group flex w-full items-center rounded-lg px-3 py-2 text-xs
                                        font-medium transition-colors`,
                                    ]"
                                    @click="$emit('delete-template', template.id)"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsDeleteRounded"
                                        class="mr-2 h-4 w-4 opacity-70"
                                    />
                                    Delete
                                </button>
                            </HeadlessMenuItem>
                        </div>
                    </HeadlessMenuItems>
                </transition>
            </HeadlessMenu>
        </div>
    </li>
</template>
