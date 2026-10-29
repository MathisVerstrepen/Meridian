<script setup lang="ts">
import type { AgentTeam } from '@/types/agent';
defineProps<{
    teams: AgentTeam[];
    activeIndex: number;
    listId: string;
    query: string;
    loading: boolean;
    error: string;
    memberCount: (team: AgentTeam) => number;
}>();
defineEmits<{ choose: [team: AgentTeam]; active: [index: number]; retry: [] }>();
</script>

<template>
    <div
        class="bg-anthracite text-soft-silk border-stone-gray/20 absolute bottom-full left-0 z-30
            mb-3 w-full max-w-full overflow-hidden rounded-2xl border shadow-xl sm:w-96"
        data-testid="team-mention-menu"
        @mousedown.prevent
    >
        <div class="border-stone-gray/10 flex items-center gap-2 border-b px-4 py-3">
            <UiIcon name="MaterialSymbolsAltRouteRounded" class="text-ember-glow size-4" />
            <span class="text-sm font-semibold">Mention a Team</span>
            <span v-if="!loading && !error" class="text-stone-gray/60 ml-auto text-xs"
                >{{ teams.length }} {{ teams.length === 1 ? 'match' : 'matches' }}</span
            >
        </div>
        <p
            v-if="loading"
            role="status"
            class="text-stone-gray flex items-center gap-2 px-4 py-5 text-sm"
        >
            <UiIcon name="LineMdLoadingTwotoneLoop" class="size-4" />Loading your Teams…
        </p>
        <div v-else-if="error" role="alert" class="space-y-2 px-4 py-4 text-sm">
            <p class="text-stone-gray">{{ error }}</p>
            <button
                type="button"
                class="text-ember-glow hover:bg-ember-glow/10 rounded px-2 py-1 font-medium"
                @click="$emit('retry')"
            >
                Try again
            </button>
        </div>
        <div
            :id="listId"
            role="listbox"
            aria-label="Team mentions"
            class="max-h-64 overflow-y-auto overscroll-contain p-1.5"
            :class="{ hidden: loading || !!error }"
        >
            <button
                v-for="(team, index) in teams"
                :id="`${listId}-${team.id}`"
                :key="team.id"
                type="button"
                role="option"
                tabindex="-1"
                :aria-label="`@${team.handle} · ${team.name}`"
                :aria-selected="index === activeIndex"
                class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left
                    transition-colors"
                :class="
                    index === activeIndex
                        ? 'bg-ember-glow/10 ring-ember-glow/25 ring-1 ring-inset'
                        : 'hover:bg-stone-gray/5'
                "
                @pointermove="$emit('active', index)"
                @click="$emit('choose', team)"
            >
                <span
                    class="bg-stone-gray/8 text-stone-gray flex size-9 shrink-0 items-center
                        justify-center rounded-lg"
                    ><UiIcon name="MaterialSymbolsAltRouteRounded" class="size-5"
                /></span>
                <span class="min-w-0 flex-1"
                    ><span class="flex items-center gap-2"
                        ><strong class="truncate text-sm font-semibold">{{ team.name }}</strong
                        ><span
                            v-if="team.is_default"
                            class="text-ember-glow bg-ember-glow/10 rounded px-1.5 py-0.5 text-xs"
                            >Default</span
                        ></span
                    ><span class="text-stone-gray/75 mt-0.5 block text-xs"
                        >@{{ team.handle }} · {{ memberCount(team) }}
                        {{ memberCount(team) === 1 ? 'subagent' : 'subagents' }}</span
                    ><span
                        v-if="team.description"
                        class="text-stone-gray/60 mt-1 line-clamp-1 text-xs"
                        >{{ team.description }}</span
                    ></span
                >
                <UiIcon
                    v-if="index === activeIndex"
                    name="MdiArrowUp"
                    class="text-stone-gray/60 size-4 shrink-0 rotate-90"
                />
            </button>
            <p
                v-if="!teams.length && !loading && !error"
                class="text-stone-gray/75 px-3 py-4 text-sm"
            >
                {{
                    query
                        ? `No Teams match @${query}. Try another name or handle.`
                        : 'No Teams available. Manage your Teams in Settings.'
                }}
            </p>
        </div>
        <div
            class="border-stone-gray/10 text-stone-gray/65 flex flex-wrap items-center gap-x-3
                gap-y-1 border-t px-4 py-2 text-xs"
        >
            <span><kbd class="text-stone-gray">↑ ↓</kbd> navigate</span
            ><span><kbd class="text-stone-gray">Tab / ↵</kbd> insert</span
            ><span><kbd class="text-stone-gray">Esc</kbd> close</span>
        </div>
    </div>
</template>
