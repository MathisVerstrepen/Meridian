<script setup lang="ts">
import type { AgentTeam } from '@/types/agent';
const store = useAgentStore();
const selectedId = ref('');
const creating = ref(false);
const notice = ref('');
const error = ref('');
const selected = computed(() => store.teams.find((team) => team.id === selectedId.value));
watch(
    () => store.defaultTeamId,
    (id) => {
        if (!selectedId.value && id) selectedId.value = id;
    },
    { immediate: true },
);
const choose = (team: AgentTeam) => {
    selectedId.value = team.id;
    creating.value = false;
    notice.value = '';
};
const saved = async (team: AgentTeam) => {
    selectedId.value = team.id;
    creating.value = false;
    notice.value = 'Team saved.';
    error.value = '';
    try {
        await store.loadLibrary();
    } catch {
        error.value =
            'Your Team was saved, but the list could not refresh. Reopen Teams to refresh it.';
    }
};
const availableCount = (team: AgentTeam) =>
    team.members.filter((id) =>
        store.library.some((agent) => agent.id === id && agent.profile.lifecycle === 'active'),
    ).length;
</script>

<template>
    <section
        class="grid items-start gap-5 lg:grid-cols-[16rem_minmax(0,1fr)]"
        aria-label="Manage Teams"
    >
        <div class="flex min-w-0 flex-col gap-3">
            <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                Your Teams
                <span class="text-stone-gray/70 ml-1 font-normal">{{ store.teams.length }}</span>
            </h3>
            <nav aria-label="Your Teams" class="flex flex-col gap-2">
                <button
                    v-for="team in store.teams"
                    :key="team.id"
                    type="button"
                    :aria-current="!creating && selectedId === team.id ? 'true' : undefined"
                    class="focus-visible:outline-ember-glow rounded-xl border p-3 text-left
                        transition-colors focus-visible:outline-2"
                    :class="
                        !creating && selectedId === team.id
                            ? 'border-ember-glow/50 bg-ember-glow/8'
                            : 'border-stone-gray/15 hover:bg-stone-gray/5'
                    "
                    @click="choose(team)"
                >
                    <span class="flex items-center justify-between gap-2">
                        <strong class="truncate text-sm">{{ team.name }}</strong>
                        <span
                            v-if="team.is_default"
                            class="text-ember-glow bg-ember-glow/10 rounded px-1.5 py-0.5 text-xs"
                            >Default</span
                        >
                    </span>
                    <span class="text-stone-gray/70 mt-1 block text-xs"
                        >@{{ team.handle }} · {{ availableCount(team) }} active</span
                    >
                </button>
            </nav>
            <button
                type="button"
                class="border-stone-gray/25 hover:bg-stone-gray/5 rounded-xl border px-3 py-2.5
                    text-sm font-semibold"
                @click="
                    creating = true;
                    notice = '';
                "
            >
                + Create Team
            </button>
        </div>
        <div class="min-w-0">
            <p v-if="error" role="alert" class="mb-3 text-sm text-red-400">{{ error }}</p>
            <p v-if="notice" role="status" class="text-ember-glow mb-3 text-sm">{{ notice }}</p>
            <UiLibraryAgentTeamEditor
                v-if="creating || selected"
                :key="creating ? 'new' : selected?.id"
                :team="creating ? undefined : selected"
                @saved="saved"
                @close="
                    creating = false;
                    selectedId = '';
                    notice = '';
                "
            />
            <div v-else class="border-stone-gray/15 rounded-xl border p-8 text-center">
                <UiIcon
                    name="MaterialSymbolsAltRouteRounded"
                    class="text-stone-gray/60 mx-auto mb-3 size-8"
                />
                <h3 class="font-semibold">Choose a Team</h3>
                <p class="text-stone-gray/70 mt-2 text-sm">
                    Select a Team to manage its details and subagents, or create a new one.
                </p>
            </div>
        </div>
    </section>
</template>
