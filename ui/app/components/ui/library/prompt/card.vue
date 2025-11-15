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
    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const matches = props.template.templateText.matchAll(regex);
    const variables = new Set(Array.from(matches, (m) => m[1]));
    return Array.from(variables);
});
</script>

<template>
    <li
        class="bg-anthracite/40 border-stone-gray/10 group hover:border-stone-gray/20 relative flex
            flex-col rounded-2xl border-2 p-5 pb-4 transition-all duration-200 hover:shadow-lg"
    >
        <!-- Main Content (Clickable) -->
        <div
            class="flex flex-1 cursor-pointer flex-col"
            @click="$emit('open-edit-modal', template)"
        >
            <!-- Header -->
            <div class="flex items-start justify-between gap-4">
                <h4 class="text-soft-silk text-lg leading-tight font-semibold">
                    {{ template.name }}
                </h4>
                <div
                    v-if="template.isPublic"
                    class="bg-slate-blue/20 text-slate-blue-dark dark:text-soft-silk flex-shrink-0
                        rounded-full px-2.5 py-1 text-xs font-medium"
                >
                    Public
                </div>
            </div>

            <!-- Description -->
            <p class="text-stone-gray/70 mt-2 line-clamp-3 text-sm leading-relaxed">
                {{ template.description || 'No description provided.' }}
            </p>
        </div>

        <!-- Spacer to push footer to the bottom -->
        <div class="flex-grow"></div>

        <!-- Footer -->
        <div class="mt-4 flex items-center justify-between pt-2">
            <!-- Metadata -->
            <div class="text-stone-gray/60 flex items-center justify-center gap-2 text-xs">
                <span v-if="detectedVariables.length > 0" class="font-medium">
                    {{ detectedVariables.length }} variable{{
                        detectedVariables.length > 1 ? 's' : ''
                    }}
                </span>
                -
                <NuxtTime :datetime="template.updatedAt" locale="en-US" relative />
            </div>

            <!-- Actions Menu -->
            <div class="relative">
                <HeadlessMenu as="div" class="relative inline-block text-left">
                    <div>
                        <HeadlessMenuButton
                            class="hover:bg-stone-gray/10 flex h-8 w-8 items-center justify-center
                                rounded-full transition-colors"
                            aria-label="More options"
                            @click.stop
                        >
                            <UiIcon
                                name="Fa6SolidEllipsisVertical"
                                class="text-stone-gray h-4 w-4"
                            />
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
                            class="bg-obsidian border-stone-gray/20 ring-opacity-5 absolute right-0
                                bottom-10 z-10 mt-2 w-40 origin-bottom-right rounded-md border
                                shadow-lg backdrop-blur-2xl"
                        >
                            <div class="py-1">
                                <HeadlessMenuItem v-slot="{ active }">
                                    <button
                                        :class="[
                                            active ? 'bg-stone-gray/10' : '',
                                            `text-soft-silk group flex w-full items-center px-4 py-2
                                            text-sm`,
                                        ]"
                                        @click="$emit('open-edit-modal', template)"
                                    >
                                        <UiIcon
                                            name="MaterialSymbolsEditRounded"
                                            class="mr-3 h-5 w-5"
                                        />
                                        Edit
                                    </button>
                                </HeadlessMenuItem>
                                <HeadlessMenuItem v-slot="{ active }">
                                    <button
                                        :class="[
                                            active ? 'bg-red-500/10' : '',
                                            `group flex w-full items-center px-4 py-2 text-sm
                                            text-red-400`,
                                        ]"
                                        @click="$emit('delete-template', template.id)"
                                    >
                                        <UiIcon
                                            name="MaterialSymbolsDeleteRounded"
                                            class="mr-3 h-5 w-5"
                                        />
                                        Delete
                                    </button>
                                </HeadlessMenuItem>
                            </div>
                        </HeadlessMenuItems>
                    </transition>
                </HeadlessMenu>
            </div>
        </div>
    </li>
</template>
