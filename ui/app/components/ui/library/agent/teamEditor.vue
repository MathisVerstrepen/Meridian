<script setup lang="ts">
import type { AgentTeam } from '@/types/agent';
import { suggestAgentHandle } from '@/utils/agentEditor';
const props = defineProps<{ team?: AgentTeam }>();
const emit = defineEmits<{ saved: [team: AgentTeam]; close: [] }>();
const store = useAgentStore();
const draft = ref({
    name: props.team?.name ?? '',
    handle: props.team?.handle ?? '',
    description: props.team?.description ?? '',
    members: [...(props.team?.members ?? [])],
});
const error = ref('');
const saving = ref(false);
const search = ref('');
const editedHandle = ref(!!props.team);
watch(
    () => draft.value.name,
    (name) => {
        if (!editedHandle.value)
            draft.value.handle = name.trim()
                ? suggestAgentHandle(
                      name,
                      store.teams.map((team) => team.handle),
                  )
                : '';
    },
);
const members = computed(() =>
    draft.value.members.map((id) => ({
        id,
        agent: store.library.find((agent) => agent.id === id),
    })),
);
const available = computed(() =>
    store.library.filter(
        (agent) =>
            agent.profile.lifecycle === 'active' &&
            !draft.value.members.includes(agent.id) &&
            `${agent.profile.name} ${agent.profile.description}`
                .toLowerCase()
                .includes(search.value.trim().toLowerCase()),
    ),
);
const activeCount = computed(
    () => members.value.filter(({ agent }) => agent?.profile.lifecycle === 'active').length,
);
const inputClass =
    'bg-anthracite/25 border-stone-gray/20 focus:border-ember-glow/70 w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors disabled:opacity-60';
const move = (index: number, delta: number) => {
    if (index + delta < 0 || index + delta >= draft.value.members.length) return;
    const id = draft.value.members.splice(index, 1)[0];
    if (id) draft.value.members.splice(index + delta, 0, id);
};
const save = async () => {
    if (saving.value) return;
    saving.value = true;
    error.value = '';
    try {
        const saved = await store.saveTeam(
            { ...draft.value, members: [...draft.value.members] },
            props.team?.id,
        );
        emit('saved', saved);
    } catch (err) {
        error.value = runtimeErrorDetail(err) ?? 'Could not save this Team.';
    } finally {
        saving.value = false;
    }
};
</script>

<template>
    <form
        aria-label="Team editor"
        class="border-stone-gray/15 flex flex-col gap-5 rounded-2xl border p-5"
        @submit.prevent="save"
    >
        <div class="flex items-start justify-between gap-3">
            <div>
                <h3 class="text-lg font-semibold">
                    {{ props.team ? 'Edit Team' : 'Create Team' }}
                </h3>
                <p class="text-stone-gray/70 mt-1 text-sm">
                    Choose the helpers your main model can call.
                </p>
            </div>
            <button
                type="button"
                aria-label="Close Team editor"
                :disabled="saving"
                class="text-stone-gray hover:text-soft-silk rounded-lg p-2 disabled:opacity-40"
                @click="emit('close')"
            >
                <UiIcon name="MaterialSymbolsClose" class="size-5" />
            </button>
        </div>
        <fieldset :disabled="saving" class="min-w-0 space-y-5">
            <section class="space-y-4" aria-label="Team details">
                <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                    Team details
                </h3>
                <div class="grid gap-4 sm:grid-cols-2">
                    <label class="flex flex-col gap-2 text-sm font-medium"
                        >Team name
                        <input
                            v-model="draft.name"
                            required
                            maxlength="100"
                            placeholder="e.g. Research Team"
                            :class="inputClass"
                        />
                    </label>
                    <label class="flex flex-col gap-2 text-sm font-medium"
                        >Team handle
                        <input
                            v-model="draft.handle"
                            required
                            pattern="[a-z][a-z0-9_-]{1,49}"
                            maxlength="50"
                            :disabled="props.team?.is_default"
                            :class="inputClass"
                            @input="editedHandle = true"
                        />
                    </label>
                </div>
                <p class="text-stone-gray/70 text-xs">
                    Mention
                    <span class="text-soft-silk">@{{ draft.handle || 'team-handle' }}</span> in chat
                    to select this Team.{{
                        props.team?.is_default ? ' The default handle is fixed.' : ''
                    }}
                </p>
                <label class="flex flex-col gap-2 text-sm font-medium"
                    ><span
                        >Description
                        <span class="text-stone-gray/60 text-xs font-normal">Optional</span></span
                    >
                    <textarea
                        v-model="draft.description"
                        rows="2"
                        maxlength="2000"
                        placeholder="What does this Team help with?"
                        :class="inputClass"
                    />
                </label>
                <p
                    v-if="props.team?.is_default"
                    class="bg-ember-glow/5 border-ember-glow/15 text-stone-gray/85 rounded-lg border
                        px-3 py-2.5 text-xs leading-relaxed"
                >
                    New Agents join this Team automatically. You can add or remove members here.
                </p>
            </section>
            <section class="space-y-3" aria-label="Team members">
                <h3
                    class="text-soft-silk bg-obsidian/20 flex items-center justify-between gap-2
                        rounded-lg px-3 py-1 text-sm font-bold"
                >
                    Members
                    <span class="text-stone-gray/70 text-xs font-normal"
                        >{{ activeCount }} active · {{ draft.members.length }} total</span
                    >
                </h3>
                <p class="text-stone-gray/70 text-xs leading-relaxed">
                    Order controls presentation. The main model chooses when and which subagents to
                    call.
                </p>
                <ol
                    v-if="members.length"
                    class="divide-stone-gray/10 border-stone-gray/15 divide-y rounded-xl border"
                >
                    <li
                        v-for="({ id, agent }, index) in members"
                        :key="id"
                        class="flex items-center gap-2 px-3 py-3"
                    >
                        <span class="text-stone-gray/50 w-5 shrink-0 text-center text-xs">{{
                            index + 1
                        }}</span>
                        <UiIcon name="RiBrain2Line" class="text-stone-gray/70 size-4 shrink-0" />
                        <div class="min-w-0 flex-1">
                            <p class="truncate text-sm font-medium">
                                {{ agent?.profile.name ?? 'Unavailable Agent' }}
                            </p>
                            <p
                                v-if="agent?.profile.lifecycle !== 'active'"
                                class="text-stone-gray/60 text-xs"
                            >
                                {{
                                    agent?.profile.lifecycle === 'draft'
                                        ? 'Draft · cannot execute'
                                        : 'Unavailable · cannot execute'
                                }}
                            </p>
                        </div>
                        <button
                            type="button"
                            :disabled="index === 0"
                            :aria-label="`Move ${agent?.profile.name ?? 'member'} up`"
                            class="text-stone-gray hover:bg-stone-gray/10 rounded-md p-2
                                disabled:opacity-25"
                            @click="move(index, -1)"
                        >
                            ↑
                        </button>
                        <button
                            type="button"
                            :disabled="index === members.length - 1"
                            :aria-label="`Move ${agent?.profile.name ?? 'member'} down`"
                            class="text-stone-gray hover:bg-stone-gray/10 rounded-md p-2
                                disabled:opacity-25"
                            @click="move(index, 1)"
                        >
                            ↓
                        </button>
                        <button
                            type="button"
                            :aria-label="`Remove ${agent?.profile.name ?? 'member'}`"
                            class="text-stone-gray rounded-md p-2 hover:text-red-400"
                            @click="draft.members.splice(index, 1)"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="size-4" />
                        </button>
                    </li>
                </ol>
                <p
                    v-else
                    class="border-stone-gray/20 text-stone-gray/70 rounded-xl border border-dashed
                        p-5 text-center text-sm"
                >
                    No members yet. Add an Agent below to get started.
                </p>
                <div class="bg-obsidian/10 border-stone-gray/10 space-y-3 rounded-xl border p-3">
                    <label class="flex flex-col gap-2 text-sm font-medium"
                        >Add Agents
                        <input
                            v-model="search"
                            type="search"
                            placeholder="Search your active Agents…"
                            :class="inputClass"
                        />
                    </label>
                    <ul v-if="available.length" class="max-h-48 space-y-1 overflow-y-auto">
                        <li
                            v-for="agent in available"
                            :key="agent.id"
                            class="hover:bg-stone-gray/5 flex items-center gap-3 rounded-lg px-2
                                py-2"
                        >
                            <div class="min-w-0 flex-1">
                                <p class="text-sm">{{ agent.profile.name }}</p>
                                <p class="text-stone-gray/60 line-clamp-1 text-xs">
                                    {{ agent.profile.description }}
                                </p>
                            </div>
                            <button
                                type="button"
                                :aria-label="`Add ${agent.profile.name}`"
                                class="border-stone-gray/25 hover:border-ember-glow/50
                                    text-ember-glow rounded-lg border px-3 py-1.5 text-xs
                                    font-semibold"
                                @click="draft.members.push(agent.id)"
                            >
                                + Add
                            </button>
                        </li>
                    </ul>
                    <p v-else class="text-stone-gray/60 py-2 text-xs">
                        {{
                            search.trim()
                                ? 'No matching Agents.'
                                : store.library.some(
                                        (agent) => agent.profile.lifecycle === 'active',
                                    )
                                  ? 'All active Agents are already in this Team.'
                                  : 'Create and activate an Agent in your library to add it here.'
                        }}
                    </p>
                </div>
            </section>
        </fieldset>
        <p v-if="error" role="alert" class="text-sm text-red-400">{{ error }}</p>
        <div class="border-stone-gray/15 flex items-center justify-end gap-3 border-t pt-4">
            <button
                type="button"
                :disabled="saving"
                class="text-stone-gray hover:text-soft-silk rounded-lg px-4 py-2 text-sm
                    disabled:opacity-40"
                @click="emit('close')"
            >
                Cancel
            </button>
            <button
                :disabled="saving"
                class="bg-ember-glow hover:bg-ember-glow/85 rounded-lg px-4 py-2 text-sm
                    font-semibold disabled:opacity-50"
            >
                {{ saving ? 'Saving…' : 'Save Team' }}
            </button>
        </div>
    </form>
</template>
