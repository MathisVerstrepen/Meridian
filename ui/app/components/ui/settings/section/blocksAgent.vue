<script setup lang="ts">
import type { AgentProfile, AgentRecord, AgentTeam } from '@/types/agent';
const store = useAgentStore();
const { user } = useUserSession();
const view = ref('my');
const q = ref('');
const category = ref('');
const model = ref('');
const tool = ref('');
const sort = ref('updated');
const offset = ref(0);
const editing = ref<AgentRecord>();
const preset = ref<AgentProfile>();
const showEditor = ref(false);
const filtersOpen = ref(false);
const isEmptyLibrary = computed(
    () => view.value === 'my' && !q.value && !store.loading && !store.library.length,
);
const formHost = ref<HTMLElement | null>(null);
const showTeams = ref(useRoute().query.view === 'teams');
const team = ref<AgentTeam>();
const showTeamEditor = ref(false);
const preview = ref<AgentRecord>();
const error = ref('');
const starterPresets = ref<AgentProfile[]>([]);
const views = [
    ['my', 'My Agents'],
    ['bookmarked', 'Bookmarked'],
    ['forked', 'Forked'],
    ['recent', 'Recently Used'],
    ['team', 'Team Agents'],
    ['marketplace', 'Marketplace'],
    ['drafts', 'Drafts'],
];
const refresh = () =>
    store.search({
        view: view.value,
        q: q.value,
        category: category.value,
        model: model.value,
        tool: tool.value,
        sort: sort.value,
        offset: offset.value,
    });
watch([view, q, category, model, tool, sort], () => {
    offset.value = 0;
    refresh();
});
watch(offset, refresh);
onMounted(async () => {
    await Promise.all([refresh(), store.loadLibrary()]);
    starterPresets.value = await store.presets();
});
const perform = async <T,>(action: () => Promise<T>) => {
    error.value = '';
    try {
        await action();
        await Promise.all([refresh(), store.loadLibrary()]);
    } catch (err) {
        error.value = runtimeErrorDetail(err) ?? 'Could not complete this action.';
    }
};
const edit = (agent?: AgentRecord, starter?: AgentProfile) => {
    editing.value = agent;
    preset.value = starter;
    showEditor.value = true;
    preview.value = undefined;
    nextTick(() => {
        formHost.value?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
};
const saved = async () => {
    showEditor.value = false;
    showTeamEditor.value = false;
    await perform(async () => {});
};
const exportAgent = async (agent: AgentRecord) => {
    const body = await store.exportProfile(agent.id);
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = `${agent.handle}.json`;
    link.click();
    URL.revokeObjectURL(url);
};
const importFile = async (event: Event) => {
    const file = event.target instanceof HTMLInputElement ? event.target.files?.[0] : undefined;
    if (!file) return;
    await perform(async () => {
        if (file.size > 2000000) throw new Error('Agent import must be under 2 MB.');
        const value: unknown = JSON.parse(await file.text());
        if (!isJsonObject(value)) throw new Error('Expected an Agent JSON object.');
        await store.importProfile(value);
    });
};
</script>

<template>
    <section ref="formHost" class="text-soft-silk flex flex-col gap-5 py-5">
        <UiLibraryAgentEditor
            v-if="showEditor"
            :key="editing?.id ?? preset?.handle ?? 'new'"
            :agent="editing"
            :preset="preset"
            :presets="starterPresets"
            @saved="saved"
            @close="showEditor = false"
        />
        <template v-else>
            <div class="flex flex-wrap items-center gap-3">
                <div class="mr-auto">
                    <h2 class="text-xl font-semibold">Your Agent library</h2>
                    <p class="text-stone-gray/65 mt-1 text-sm">
                        Build a team of helpers for the way you work.
                    </p>
                </div>
                <button
                    class="bg-ember-glow hover:bg-ember-glow/85 rounded-xl px-4 py-2.5 text-sm
                        font-semibold transition-colors"
                    @click="edit()"
                >
                    + Create Agent
                </button>
                <label
                    class="border-stone-gray/20 text-stone-gray hover:bg-stone-gray/5 cursor-pointer
                        rounded-xl border px-4 py-2.5 text-sm"
                    >Import JSON
                    <input
                        type="file"
                        accept="application/json,.json"
                        class="sr-only"
                        @change="importFile"
                /></label>
                <button
                    class="border-stone-gray/20 text-stone-gray hover:bg-stone-gray/5 rounded-xl
                        border px-4 py-2.5 text-sm"
                    @click="showTeams = !showTeams"
                >
                    {{ showTeams ? 'Agent library' : 'Manage Teams' }}
                </button>
            </div>
            <template v-if="showTeams">
                <button
                    class="self-start rounded-lg border px-4 py-2"
                    @click="
                        team = undefined;
                        showTeamEditor = true;
                    "
                >
                    Create Team
                </button>
                <UiLibraryAgentTeamEditor
                    v-if="showTeamEditor"
                    :key="team?.id ?? 'new'"
                    :team="team"
                    @saved="saved"
                    @close="showTeamEditor = false"
                />
                <button
                    v-for="entry in store.teams"
                    :key="entry.id"
                    class="border-stone-gray/20 rounded-lg border p-4 text-left"
                    @click="
                        team = entry;
                        showTeamEditor = true;
                    "
                >
                    <strong>{{ entry.name }}</strong>
                    <span
                        v-if="entry.is_default"
                        class="bg-ember-glow/10 text-ember-glow ml-2 rounded-full px-2 py-0.5
                            text-xs"
                        >Default</span
                    >
                    · {{ entry.members.length }} members
                    <p class="mt-1 text-xs opacity-70">@{{ entry.handle }}</p>
                    <p>{{ entry.description }}</p>
                </button>
            </template>
            <template v-else>
                <nav aria-label="Agent library views" class="flex flex-wrap gap-2">
                    <button
                        v-for="[value, label] in views"
                        :key="value"
                        class="rounded-lg px-3 py-2 text-sm"
                        :class="view === value ? 'bg-ember-glow' : 'bg-anthracite'"
                        :aria-current="view === value ? 'page' : undefined"
                        @click="view = value ?? 'my'"
                    >
                        {{ label }}
                    </button>
                </nav>
                <div v-if="!isEmptyLibrary" class="flex flex-wrap items-center gap-3">
                    <input
                        v-model="q"
                        aria-label="Search Agents"
                        placeholder="Search your Agents…"
                        class="bg-anthracite/25 border-stone-gray/20 focus:border-ember-glow/70
                            min-w-48 flex-1 rounded-xl border px-3.5 py-2.5 text-sm outline-none"
                    />
                    <button
                        class="border-stone-gray/20 text-stone-gray rounded-xl border px-3 py-2.5
                            text-sm"
                        :aria-expanded="filtersOpen"
                        @click="filtersOpen = !filtersOpen"
                    >
                        Filters
                    </button>
                    <select
                        v-model="sort"
                        aria-label="Sort Agents"
                        class="bg-anthracite/25 border-stone-gray/20 text-stone-gray rounded-xl
                            border p-2.5 text-sm"
                    >
                        <option value="updated">Recently updated</option>
                        <option value="newest">Newest</option>
                        <option value="name">Name</option>
                        <option value="rating">Highest rated</option>
                        <option value="bookmarks">Most bookmarked</option>
                        <option value="forks">Most forked</option>
                        <option value="usage">Most used</option>
                    </select>
                </div>
                <div v-if="filtersOpen" class="grid gap-3 sm:grid-cols-3">
                    <label
                        v-for="filter in ['Category', 'Model', 'Tool']"
                        :key="filter"
                        class="text-stone-gray/70 text-xs"
                        >{{ filter }}
                        <input
                            v-if="filter === 'Category'"
                            v-model="category"
                            aria-label="Filter category"
                            class="bg-anthracite/25 border-stone-gray/20 mt-1 w-full rounded-xl
                                border p-2.5 text-sm"
                        />
                        <input
                            v-else-if="filter === 'Model'"
                            v-model="model"
                            aria-label="Filter model"
                            class="bg-anthracite/25 border-stone-gray/20 mt-1 w-full rounded-xl
                                border p-2.5 text-sm"
                        />
                        <input
                            v-else
                            v-model="tool"
                            aria-label="Filter tool"
                            class="bg-anthracite/25 border-stone-gray/20 mt-1 w-full rounded-xl
                                border p-2.5 text-sm"
                        />
                    </label>
                </div>
                <div
                    v-if="isEmptyLibrary"
                    class="border-stone-gray/15 bg-anthracite/10 rounded-2xl border p-6"
                >
                    <UiIcon name="RiBrain2Line" class="text-ember-glow mb-4 size-8" />
                    <h3 class="text-lg font-semibold">Meet your next go-to helper</h3>
                    <p class="text-stone-gray/70 mt-2 max-w-xl text-sm leading-relaxed">
                        Give an Agent a role once, then use it across your graphs and chats. Start
                        from a template or create one from scratch.
                    </p>
                    <button class="text-ember-glow mt-4 text-sm font-semibold" @click="edit()">
                        Create a custom Agent →
                    </button>
                    <div
                        v-if="starterPresets.length"
                        class="border-stone-gray/10 mt-6 border-t pt-5"
                    >
                        <p
                            class="text-stone-gray/55 mb-3 text-xs font-medium tracking-wider
                                uppercase"
                        >
                            Start with a template
                        </p>
                        <UiLibraryAgentStarterTemplates
                            :presets="starterPresets"
                            @choose="(starter) => edit(undefined, starter)"
                        />
                    </div>
                </div>
                <p v-if="store.loading" role="status">Loading Agents…</p>
                <p v-else-if="!store.items.length && !isEmptyLibrary">
                    No Agents found. Create an Agent or start from a preset below.
                </p>
                <div class="grid gap-4 lg:grid-cols-2">
                    <UiLibraryAgentCard
                        v-for="agent in store.items"
                        :key="agent.id"
                        :agent="agent"
                        :owned="store.library.some((item) => item.id === agent.id)"
                        @preview="preview = agent"
                        @edit="edit(agent)"
                        @fork="perform(() => store.fork(agent.id))"
                        @bookmark="perform(() => store.bookmark(agent))"
                        @export="perform(() => exportAgent(agent))"
                        @archive="
                            perform(() =>
                                store.save({ ...agent.profile, lifecycle: 'archived' }, agent.id),
                            )
                        "
                        @restore="
                            perform(() =>
                                store.save({ ...agent.profile, lifecycle: 'active' }, agent.id),
                            )
                        "
                        @remove="perform(() => store.remove(agent.id))"
                    />
                </div>
                <div v-if="store.total > 24" class="flex items-center justify-between">
                    <button
                        :disabled="offset === 0"
                        class="disabled:opacity-40"
                        @click="offset = Math.max(0, offset - 24)"
                    >
                        Previous
                    </button>
                    <span class="text-sm"
                        >{{ store.total ? offset + 1 : 0 }}–{{
                            Math.min(offset + 24, store.total)
                        }}
                        of {{ store.total }}</span
                    >
                    <button
                        :disabled="offset + 24 >= store.total"
                        class="disabled:opacity-40"
                        @click="offset += 24"
                    >
                        Next
                    </button>
                </div>
                <details v-if="preview" open class="border-stone-gray/20 rounded-xl border p-5">
                    <summary class="font-semibold">{{ preview.profile.name }} · Preview</summary>
                    <p class="mt-2">{{ preview.profile.description }}</p>
                    <p class="mt-2 text-sm">
                        Model: {{ preview.profile.model_settings.model }} · Tools:
                        {{ preview.profile.tools.join(', ') || 'None' }}
                    </p>
                    <p v-if="preview.source_id" class="mt-2 text-xs">
                        Forked from {{ preview.source_id }} v{{ preview.source_version }}
                    </p>
                    <div
                        v-for="(layer, index) in preview.profile.prompt_stack"
                        :key="index"
                        class="mt-3"
                    >
                        <strong>{{ layer.name }} {{ layer.enabled ? '' : '(disabled)' }}</strong>
                        <p class="text-sm whitespace-pre-wrap">{{ layer.text }}</p>
                    </div>
                    <label class="mt-4 block"
                        >Your rating
                        <select
                            :value="preview.my_rating ?? ''"
                            class="bg-anthracite rounded-lg p-2"
                            @change="
                                perform(() =>
                                    store.rate(
                                        preview!.id,
                                        Number(($event.target as HTMLSelectElement).value),
                                    ),
                                )
                            "
                        >
                            <option value="" disabled>Rate 1–5</option>
                            <option v-for="rating in 5" :key="rating" :value="rating">
                                {{ rating }}
                            </option>
                        </select>
                    </label>
                    <button
                        v-if="user?.is_admin"
                        class="mt-3 underline"
                        @click="perform(() => store.verify(preview!.id, !preview!.verified))"
                    >
                        {{ preview.verified ? 'Remove verification' : 'Verify by Meridian' }}
                    </button>
                </details>
                <details
                    v-if="!isEmptyLibrary && starterPresets.length"
                    class="group border-stone-gray/15 rounded-xl border p-4"
                >
                    <summary class="text-stone-gray cursor-pointer text-sm">
                        Explore starter templates
                    </summary>
                    <UiLibraryAgentStarterTemplates
                        class="mt-4"
                        :presets="starterPresets"
                        @choose="(starter) => edit(undefined, starter)"
                    />
                </details>
            </template>
            <p v-if="error || store.error" role="alert" class="text-red-400">
                {{ error || store.error }}
            </p>
        </template>
    </section>
</template>
