<script setup lang="ts">
import type { AgentTeam } from '@/types/agent';
import { suggestAgentHandle } from '@/utils/agentEditor';
const props = defineProps<{ team?: AgentTeam }>();
const emit = defineEmits<{ saved: []; close: [] }>();
const store = useAgentStore();
const empty: Pick<AgentTeam, 'name' | 'handle' | 'description' | 'members'> = {
    name: '',
    handle: '',
    description: '',
    members: [],
};
const draft = ref({
    name: props.team?.name ?? empty.name,
    handle: props.team?.handle ?? empty.handle,
    description: props.team?.description ?? empty.description,
    members: [...(props.team?.members ?? empty.members)],
});
const error = ref('');
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
const selected = ref('');
const move = (index: number, delta: number) => {
    const id = draft.value.members.splice(index, 1)[0];
    if (id) draft.value.members.splice(index + delta, 0, id);
};
const save = async () => {
    try {
        await store.saveTeam(draft.value, props.team?.id);
        emit('saved');
    } catch (err) {
        error.value = runtimeErrorDetail(err) ?? 'Could not save this Team.';
    }
};
</script>

<template>
    <form
        class="border-stone-gray/20 flex flex-col gap-4 rounded-xl border p-5"
        @submit.prevent="save"
    >
        <div class="flex justify-between">
            <h3 class="font-semibold">{{ props.team ? 'Edit Team' : 'Create Team' }}</h3>
            <button type="button" @click="emit('close')">Close</button>
        </div>
        <label class="flex flex-col gap-1"
            >Team name <input v-model="draft.name" required class="bg-anthracite rounded-lg p-2"
        /></label>
        <label class="flex flex-col gap-1">
            Team handle
            <input
                v-model="draft.handle"
                required
                pattern="[a-z][a-z0-9_-]{1,49}"
                maxlength="50"
                :disabled="props.team?.is_default"
                class="bg-anthracite rounded-lg p-2"
                @input="editedHandle = true"
            />
            <span class="text-xs opacity-70"
                >Mention @{{ draft.handle || 'team-handle' }} in chat to select this Team.</span
            >
        </label>
        <p v-if="props.team?.is_default" class="text-sm opacity-70">
            New Agents are added to this Team automatically. You can edit its membership here.
        </p>
        <label class="flex flex-col gap-1"
            >Description
            <textarea v-model="draft.description" class="bg-anthracite rounded-lg p-2" />
        </label>
        <p class="text-sm opacity-70">
            Members are available subagents. Their order controls presentation; the main model
            chooses execution order.
        </p>
        <div v-for="(id, index) in draft.members" :key="id" class="flex items-center gap-3">
            <span class="flex-1">{{
                store.library.find((a) => a.id === id)?.profile.name ?? id
            }}</span>
            <button
                type="button"
                :disabled="index === 0"
                aria-label="Move member up"
                @click="move(index, -1)"
            >
                ↑
            </button>
            <button
                type="button"
                :disabled="index === draft.members.length - 1"
                aria-label="Move member down"
                @click="move(index, 1)"
            >
                ↓
            </button>
            <button type="button" @click="draft.members.splice(index, 1)">Remove</button>
        </div>
        <label class="flex flex-col gap-1"
            >Add member
            <select
                v-model="selected"
                class="bg-anthracite rounded-lg p-2"
                @change="
                    draft.members.push(selected);
                    selected = '';
                "
            >
                <option value="" disabled>Choose an active Agent</option>
                <option
                    v-for="agent in store.library.filter(
                        (a) => a.profile.lifecycle === 'active' && !draft.members.includes(a.id),
                    )"
                    :key="agent.id"
                    :value="agent.id"
                >
                    {{ agent.profile.name }}
                </option>
            </select>
        </label>
        <p v-if="error" role="alert" class="text-red-400">{{ error }}</p>
        <button class="bg-ember-glow self-start rounded-lg px-4 py-2">Save Team</button>
    </form>
</template>
