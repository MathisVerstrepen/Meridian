<script setup lang="ts">
import type { AgentRecord } from '@/types/agent';
defineProps<{ agent: AgentRecord; owned: boolean; selected?: boolean; previewId?: string }>();
const more = ref<HTMLDetailsElement | null>(null);
const closeMenu = () => {
    if (more.value) more.value.open = false;
};
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
        :class="
            selected
                ? 'border-ember-glow/50 bg-ember-glow/3'
                : 'border-stone-gray/15 hover:border-stone-gray/30'
        "
        class="flex flex-col gap-4 rounded-2xl border p-5 transition-colors"
    >
        <button
            type="button"
            :aria-label="`Preview ${agent.profile.name}`"
            :aria-expanded="!!selected"
            :aria-controls="selected ? previewId : undefined"
            class="focus-visible:outline-ember-glow flex items-start gap-3 rounded text-left
                focus-visible:outline-2"
            @click="$emit('preview')"
        >
            <span
                class="flex size-10 shrink-0 items-center justify-center rounded-xl"
                :style="{
                    color: agent.profile.accentColor,
                    backgroundColor: `${agent.profile.accentColor}1a`,
                }"
            >
                <UiLibraryAgentIcon :profile="agent.profile" class="size-6" />
            </span>
            <span class="min-w-0 flex-1"
                ><strong class="block text-base">{{ agent.profile.name }}</strong
                ><span class="text-stone-gray/55 mt-1 block text-xs"
                    >Version {{ agent.version }} ·
                    {{ agent.profile.visibility === 'public' ? 'Public' : 'Private' }}</span
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
        <span v-if="agent.verified" class="text-ember-glow inline-flex items-center gap-1 text-xs"
            ><UiIcon name="MaterialSymbolsCheckCircleOutlineRounded" class="size-4" />Verified by
            Meridian</span
        >
        <p class="text-stone-gray/60 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            <span class="inline-flex items-center gap-1"
                ><UiIcon name="MaterialSymbolsAccountCircle" class="size-3.5" />{{
                    agent.author
                }}</span
            >
            <span class="inline-flex items-center gap-1"
                ><UiIcon name="MaterialSymbolsStarOutlineRounded" class="size-3.5" />{{
                    agent.rating_count
                        ? `${agent.rating_average.toFixed(1)} (${agent.rating_count})`
                        : 'No ratings'
                }}</span
            >
            <span class="inline-flex items-center gap-1"
                ><UiIcon name="MaterialSymbolsHistory" class="size-3.5" />{{
                    agent.usage_count
                }}
                uses</span
            >
        </p>
        <div class="border-stone-gray/10 flex flex-wrap items-center gap-3 border-t pt-3 text-xs">
            <button
                v-if="owned"
                type="button"
                class="text-ember-glow inline-flex items-center gap-1.5 rounded py-1 font-semibold"
                @click="$emit('edit')"
            >
                <UiIcon name="MaterialSymbolsEditRounded" class="size-3.5" /> Edit Agent
            </button>
            <button
                v-else
                type="button"
                class="text-ember-glow inline-flex items-center gap-1.5 rounded py-1 font-semibold"
                @click="$emit('fork')"
            >
                <UiIcon name="Fa6SolidPlus" class="size-3.5" /> Add to my library
            </button>
            <button
                type="button"
                class="text-stone-gray hover:text-soft-silk inline-flex items-center gap-1.5 rounded
                    py-1"
                @click="$emit('preview')"
            >
                <UiIcon name="MdiEyeOutline" class="size-3.5" /> Preview
            </button>
            <button
                type="button"
                class="text-stone-gray hover:text-soft-silk inline-flex items-center gap-1.5 rounded
                    py-1"
                :aria-pressed="agent.bookmarked"
                @click="$emit('bookmark')"
            >
                <UiIcon name="MdiBookmarkOutline" class="size-3.5" />{{
                    agent.bookmarked ? 'Bookmarked' : 'Bookmark'
                }}
            </button>
            <details ref="more" class="relative ml-auto" @keydown.esc.stop="closeMenu">
                <summary
                    class="text-stone-gray/65 hover:text-soft-silk cursor-pointer list-none
                        rounded-lg px-2 py-1"
                    :aria-label="`More actions for ${agent.profile.name}`"
                >
                    <UiIcon name="Fa6SolidEllipsisVertical" class="size-4" />
                </summary>
                <div
                    @click="closeMenu"
                    class="bg-obsidian border-stone-gray/20 absolute right-0 z-20 mt-2 flex w-40
                        flex-col rounded-xl border p-1.5 shadow-xl"
                >
                    <button
                        v-if="owned"
                        type="button"
                        class="hover:bg-stone-gray/10 flex items-center gap-2 rounded-lg px-3 py-2
                            text-left"
                        @click="$emit('fork')"
                    >
                        <UiIcon name="MaterialSymbolsContentCopyOutlineRounded" class="size-3.5" />
                        Duplicate
                    </button>
                    <button
                        type="button"
                        class="hover:bg-stone-gray/10 flex items-center gap-2 rounded-lg px-3 py-2
                            text-left"
                        @click="$emit('export')"
                    >
                        <UiIcon name="MaterialSymbolsDownloadRounded" class="size-3.5" /> Export
                        JSON
                    </button>
                    <button
                        v-if="owned && agent.profile.lifecycle !== 'archived'"
                        type="button"
                        class="hover:bg-stone-gray/10 flex items-center gap-2 rounded-lg px-3 py-2
                            text-left"
                        @click="$emit('archive')"
                    >
                        <UiIcon name="MaterialSymbolsBlockOutline" class="size-3.5" /> Archive
                    </button>
                    <template v-if="owned && agent.profile.lifecycle === 'archived'">
                        <button
                            type="button"
                            class="hover:bg-stone-gray/10 flex items-center gap-2 rounded-lg px-3
                                py-2 text-left"
                            @click="$emit('restore')"
                        >
                            <UiIcon name="MaterialSymbolsRefreshRounded" class="size-3.5" /> Restore
                        </button>
                        <button
                            type="button"
                            class="hover:bg-stone-gray/10 flex items-center gap-2 rounded-lg px-3
                                py-2 text-left text-red-400"
                            @click="$emit('remove')"
                        >
                            <UiIcon name="MaterialSymbolsDeleteRounded" class="size-3.5" /> Delete
                        </button>
                    </template>
                </div>
            </details>
        </div>
    </article>
</template>
