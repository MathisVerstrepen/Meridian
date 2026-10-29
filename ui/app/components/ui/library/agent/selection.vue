<script setup lang="ts">
import type { ToolEnum } from '@/types/enums';
import type { AgentTeam } from '@/types/agent';
const props = defineProps<{
    model: string;
    teamId: string;
    selectedTools: ToolEnum[];
    compact?: boolean;
    autoSelectTools?: boolean;
}>();
const emit = defineEmits<{
    model: [model: string];
    team: [id: string];
}>();
const store = useAgentStore();
const error = ref('');
const teamSelectId = `agent-team-${useId()}`;
const selectedTeam = computed(() =>
    store.teams.find((team) => team.id === (props.teamId || store.defaultTeamId)),
);
const activeAgentIds = computed(
    () =>
        new Set(
            store.library
                .filter((agent) => agent.profile.lifecycle === 'active')
                .map((agent) => agent.id),
        ),
);
const teamMemberCount = (team: AgentTeam) =>
    team.members.filter((id) => activeAgentIds.value.has(id)).length;
const eligibleCount = computed(() =>
    selectedTeam.value ? teamMemberCount(selectedTeam.value) : 0,
);
watch(
    [() => props.teamId, () => store.defaultTeamId],
    ([selected, defaultId]) => {
        if (!selected && defaultId) emit('team', defaultId);
    },
    { immediate: true },
);
const eligibleMembers = computed(
    () =>
        selectedTeam.value?.members.flatMap((id) => {
            const agent = store.library.find((item) => item.id === id);
            return agent?.profile.lifecycle === 'active' ? [agent] : [];
        }) ?? [],
);
const loadTeams = async () => {
    error.value = '';
    try {
        await store.loadLibrary();
    } catch {
        error.value = 'Could not load your Teams.';
    }
};
onMounted(loadTeams);
</script>

<template>
    <div
        class="nodrag"
        :class="
            props.compact
                ? 'text-obsidian grid grid-cols-2 gap-3'
                : 'text-soft-silk flex flex-col gap-6'
        "
    >
        <section class="flex min-w-0 flex-col gap-2" aria-label="Main model">
            <div v-if="props.compact" class="text-sm">Main model</div>
            <h3 v-else class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                Main model
            </h3>
            <UiModelsSelect
                :model="props.model"
                :set-model="(model: string) => emit('model', model)"
                :disabled="false"
                :class="props.compact ? 'h-9' : ''"
                :variant="props.compact ? 'sand' : 'grey'"
                to="right"
                from="bottom"
                prevent-trigger-on-mount
                :require-meridian-tools="
                    eligibleCount > 0 || !!props.autoSelectTools || !!props.selectedTools.length
                "
                :pin-exacto-models="!!props.autoSelectTools || !!props.selectedTools.length"
                :required-tool-names="props.autoSelectTools ? [] : props.selectedTools"
            />
            <p v-if="!props.compact" class="text-stone-gray/80 text-xs leading-relaxed">
                Writes the final response using any subagent findings.
            </p>
        </section>
        <section class="flex min-w-0 flex-col gap-2" aria-label="Subagent Team">
            <label v-if="props.compact" :for="teamSelectId" class="text-sm">Team</label>
            <h3
                v-else
                class="text-soft-silk bg-obsidian/20 flex items-center justify-between gap-2
                    rounded-lg px-3 py-1 text-sm font-bold"
            >
                <label :for="teamSelectId">Team</label>
                <NuxtLink
                    to="/settings?tab=Agent&view=teams"
                    class="text-ember-glow hover:text-ember-glow/80 inline-flex shrink-0
                        items-center gap-1 rounded text-xs font-medium hover:underline
                        focus-visible:outline-2 focus-visible:outline-offset-2"
                    aria-label="Manage Agent Teams"
                >
                    Manage Teams <UiIcon name="MdiArrowTopRightThick" class="size-3" />
                </NuxtLink>
            </h3>
            <select
                :id="teamSelectId"
                :value="props.teamId || store.defaultTeamId"
                required
                :disabled="!store.teams.length"
                class="focus-visible:border-ember-glow/70 w-full rounded-2xl border-2 text-sm
                    transition-colors outline-none disabled:opacity-60"
                :class="
                    props.compact
                        ? 'bg-soft-silk/50 border-obsidian/30 text-obsidian h-9 px-2'
                        : 'bg-obsidian/20 text-soft-silk border-stone-gray/20 h-10 px-3'
                "
                aria-label="Agent Team"
                @change="emit('team', ($event.target as HTMLSelectElement).value)"
            >
                <option v-if="!store.teams.length" value="" disabled>Loading your Teams…</option>
                <option v-for="team in store.teams" :key="team.id" :value="team.id">
                    {{ team.name }} ({{ teamMemberCount(team) }}
                    {{ teamMemberCount(team) === 1 ? 'subagent' : 'subagents' }})
                </option>
            </select>
            <template v-if="!props.compact && !error && store.teams.length">
                <div
                    v-if="eligibleMembers.length"
                    aria-label="Team members"
                    class="flex flex-wrap gap-1.5"
                >
                    <span
                        v-for="agent in eligibleMembers"
                        :key="agent.id"
                        :title="agent.profile.description"
                        class="bg-stone-gray/8 text-soft-silk/85 rounded-lg px-2 py-1 text-xs"
                    >
                        {{ agent.profile.name }}
                    </span>
                </div>
                <p class="text-stone-gray/80 text-xs leading-relaxed">
                    {{
                        eligibleCount
                            ? 'The main model decides when to ask this Team for help.'
                            : 'No active subagents in this Team. Manage Teams to add one.'
                    }}
                </p>
            </template>
            <div v-if="error" class="flex items-center justify-between gap-2 text-xs" role="alert">
                <span class="text-red-400">{{ error }}</span>
                <button
                    type="button"
                    class="text-ember-glow shrink-0 rounded px-2 py-1 hover:underline"
                    @click="loadTeams"
                >
                    Try again
                </button>
            </div>
        </section>
    </div>
</template>
