<script setup lang="ts">
import type { AgentRecord } from '@/types/agent';
defineProps<{ agent: AgentRecord; owned: boolean }>();
defineEmits<{
    preview: [];
    edit: [];
    fork: [];
    bookmark: [];
    export: [];
    archive: [];
    restore: [];
    remove: [];
}>();
</script>

<template>
    <article
        class="border-stone-gray/15 hover:border-stone-gray/30 flex flex-col gap-4 rounded-2xl
            border p-5 transition-colors"
    >
        <button type="button" class="flex items-start gap-3 text-left" @click="$emit('preview')">
            <span
                class="flex size-10 shrink-0 items-center justify-center rounded-xl"
                :style="{
                    color: agent.profile.accentColor,
                    backgroundColor: `${agent.profile.accentColor}1a`,
                }"
            >
                <UiIcon
                    :name="agent.profile.icon === 'LucideBot' ? 'RiBrain2Line' : agent.profile.icon"
                    class="size-6"
                />
            </span>
            <span class="min-w-0 flex-1"
                ><strong class="block text-base">{{ agent.profile.name }}</strong
                ><span class="text-stone-gray/55 mt-1 block text-xs"
                    >@{{ agent.handle }} · v{{ agent.version }}</span
                ></span
            >
            <span class="text-stone-gray/65 bg-stone-gray/5 rounded-full px-2 py-1 text-xs">{{
                agent.profile.lifecycle === 'active'
                    ? 'Ready'
                    : agent.profile.lifecycle === 'draft'
                      ? 'Draft'
                      : 'Archived'
            }}</span>
        </button>
        <p class="text-stone-gray/75 line-clamp-2 flex-1 text-sm leading-relaxed">
            {{ agent.profile.description || 'A dedicated helper for your workflow.' }}
        </p>
        <span v-if="agent.verified" class="text-ember-glow text-xs">✓ Verified by Meridian</span>
        <p class="text-stone-gray/45 text-xs">
            By {{ agent.author }} · {{ agent.rating_average.toFixed(1) }} / 5 ({{
                agent.rating_count
            }}) · {{ agent.usage_count }} uses
        </p>
        <div class="border-stone-gray/10 flex flex-wrap items-center gap-3 border-t pt-3 text-xs">
            <button
                v-if="owned"
                type="button"
                class="text-ember-glow font-semibold"
                @click="$emit('edit')"
            >
                Edit Agent
            </button>
            <button
                v-else
                type="button"
                class="text-ember-glow font-semibold"
                @click="$emit('fork')"
            >
                Add to my library
            </button>
            <button
                type="button"
                class="text-stone-gray hover:text-soft-silk"
                @click="$emit('preview')"
            >
                Preview
            </button>
            <button
                type="button"
                class="text-stone-gray hover:text-soft-silk"
                @click="$emit('bookmark')"
            >
                {{ agent.bookmarked ? 'Bookmarked ✓' : 'Bookmark' }}
            </button>
            <details class="relative ml-auto">
                <summary
                    class="text-stone-gray/65 hover:text-soft-silk cursor-pointer list-none
                        rounded-lg px-2 py-1"
                    :aria-label="`More actions for ${agent.profile.name}`"
                >
                    More ···
                </summary>
                <div
                    class="bg-obsidian border-stone-gray/20 absolute right-0 z-20 mt-2 flex w-40
                        flex-col rounded-xl border p-1.5 shadow-xl"
                >
                    <button
                        v-if="owned"
                        type="button"
                        class="hover:bg-stone-gray/10 rounded-lg px-3 py-2 text-left"
                        @click="$emit('fork')"
                    >
                        Duplicate
                    </button>
                    <button
                        type="button"
                        class="hover:bg-stone-gray/10 rounded-lg px-3 py-2 text-left"
                        @click="$emit('export')"
                    >
                        Export JSON
                    </button>
                    <button
                        v-if="owned && agent.profile.lifecycle !== 'archived'"
                        type="button"
                        class="hover:bg-stone-gray/10 rounded-lg px-3 py-2 text-left"
                        @click="$emit('archive')"
                    >
                        Archive
                    </button>
                    <template v-if="owned && agent.profile.lifecycle === 'archived'">
                        <button
                            type="button"
                            class="hover:bg-stone-gray/10 rounded-lg px-3 py-2 text-left"
                            @click="$emit('restore')"
                        >
                            Restore
                        </button>
                        <button
                            type="button"
                            class="hover:bg-stone-gray/10 rounded-lg px-3 py-2 text-left
                                text-red-400"
                            @click="$emit('remove')"
                        >
                            Delete
                        </button>
                    </template>
                </div>
            </details>
        </div>
    </article>
</template>
