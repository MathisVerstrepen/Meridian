<script setup lang="ts">
import type { AgentRecord } from '@/types/agent';
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
const showEditor = ref(false);
const filtersOpen = ref(false);
const isEmptyLibrary = computed(
    () => view.value === 'my' && !q.value && !store.loading && !store.library.length,
);
const formHost = ref<HTMLElement | null>(null);
const showTeams = ref(useRoute().query.view === 'teams');
const preview = ref<AgentRecord>();
const previewHost = ref<HTMLElement | null>(null);
const previewPanelId = `agent-preview-${useId()}`;
const actionPending = ref(false);
let previewTrigger: HTMLElement | null = null;
const openPreview = (agent: AgentRecord) => {
    previewTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    preview.value = agent;
    error.value = '';
    nextTick(() => previewHost.value?.scrollIntoView({ block: 'start', behavior: 'smooth' }));
};
const closePreview = () => {
    preview.value = undefined;
    nextTick(() => {
        if (previewTrigger?.isConnected) previewTrigger.focus();
    });
};
const error = ref('');
const views = [
    ['my', 'My Agents', 'RiBrain2Line'],
    ['bookmarked', 'Bookmarked', 'MdiBookmarkOutline'],
    ['forked', 'Forked', 'MaterialSymbolsForkRightRounded'],
    ['recent', 'Recently Used', 'MaterialSymbolsHistory'],
    ['team', 'Team Agents', 'MaterialSymbolsAltRouteRounded'],
    ['marketplace', 'Marketplace', 'MdiWeb'],
    ['drafts', 'Drafts', 'MaterialSymbolsEditNoteOutlineRounded'],
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
});
const perform = async <T,>(action: () => Promise<T>) => {
    error.value = '';
    actionPending.value = true;
    try {
        await action();
        await Promise.all([refresh(), store.loadLibrary()]);
        if (preview.value) {
            const id = preview.value.id;
            preview.value =
                store.items.find((item) => item.id === id) ??
                store.library.find((item) => item.id === id) ??
                preview.value;
        }
    } catch (err) {
        error.value = runtimeErrorDetail(err) ?? 'Could not complete this action.';
    } finally {
        actionPending.value = false;
    }
};
const edit = (agent?: AgentRecord) => {
    editing.value = agent;
    showEditor.value = true;
    preview.value = undefined;
    nextTick(() => {
        formHost.value?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
};
const saved = async () => {
    showEditor.value = false;
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
            :key="editing?.id ?? 'new'"
            :agent="editing"
            @saved="saved"
            @close="showEditor = false"
        />
        <template v-else>
            <div class="flex flex-wrap items-center gap-3">
                <div class="mr-auto">
                    <h2 class="text-xl font-semibold">
                        {{ showTeams ? 'Agent Teams' : 'Your Agent library' }}
                    </h2>
                    <p class="text-stone-gray/65 mt-1 text-sm">
                        {{
                            showTeams
                                ? 'Choose which helpers work together in your graphs and chats.'
                                : 'Build a team of helpers for the way you work.'
                        }}
                    </p>
                </div>
                <button
                    v-if="!showTeams"
                    aria-label="+ Create Agent"
                    class="bg-ember-glow hover:bg-ember-glow/85 inline-flex items-center gap-2
                        rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors"
                    @click="edit()"
                >
                    <UiIcon name="Fa6SolidPlus" class="size-3.5" /> Create Agent
                </button>
                <label
                    v-if="!showTeams"
                    class="border-stone-gray/20 text-stone-gray hover:bg-stone-gray/5 inline-flex
                        cursor-pointer items-center gap-2 rounded-xl border px-4 py-2.5 text-sm"
                    ><UiIcon name="MdiFolderUploadOutline" class="size-4" />Import JSON
                    <input
                        type="file"
                        accept="application/json,.json"
                        class="sr-only"
                        @change="importFile"
                /></label>
                <button
                    class="border-stone-gray/20 text-stone-gray hover:bg-stone-gray/5 inline-flex
                        items-center gap-2 rounded-xl border px-4 py-2.5 text-sm"
                    @click="showTeams = !showTeams"
                >
                    <UiIcon
                        :name="showTeams ? 'RiBrain2Line' : 'MaterialSymbolsAltRouteRounded'"
                        class="size-4"
                    />
                    {{ showTeams ? 'Agent library' : 'Manage Teams' }}
                </button>
            </div>
            <UiLibraryAgentTeamsPanel v-if="showTeams" />
            <template v-else>
                <nav aria-label="Agent library views" class="flex flex-wrap gap-2">
                    <button
                        v-for="[value, label, icon] in views"
                        :key="value"
                        class="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
                        :class="view === value ? 'bg-ember-glow' : 'bg-anthracite'"
                        :aria-current="view === value ? 'page' : undefined"
                        @click="view = value ?? 'my'"
                    >
                        <UiIcon :name="icon ?? 'RiBrain2Line'" class="size-4" />{{ label }}
                    </button>
                </nav>
                <div v-if="!isEmptyLibrary" class="flex flex-wrap items-center gap-3">
                    <div class="relative min-w-48 flex-1">
                        <UiIcon
                            name="MdiMagnify"
                            class="text-stone-gray/55 pointer-events-none absolute top-1/2 left-3
                                size-4 -translate-y-1/2"
                        />
                        <input
                            v-model="q"
                            aria-label="Search Agents"
                            placeholder="Search Agents…"
                            class="bg-anthracite/25 border-stone-gray/20 focus:border-ember-glow/70
                                w-full rounded-xl border py-2.5 pr-3.5 pl-9 text-sm outline-none"
                        />
                    </div>
                    <button
                        class="border-stone-gray/20 text-stone-gray inline-flex items-center gap-2
                            rounded-xl border px-3 py-2.5 text-sm"
                        :aria-expanded="filtersOpen"
                        @click="filtersOpen = !filtersOpen"
                    >
                        <UiIcon name="MdiFilterOutline" class="size-4" /> Filters
                    </button>
                    <div class="relative">
                        <UiIcon
                            name="HeroiconsChevronUpDown16Solid"
                            class="text-stone-gray/60 pointer-events-none absolute top-1/2 left-3
                                size-4 -translate-y-1/2"
                        />
                        <select
                            v-model="sort"
                            aria-label="Sort Agents"
                            class="bg-anthracite/25 border-stone-gray/20 text-stone-gray rounded-xl
                                border py-2.5 pr-2.5 pl-9 text-sm"
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
                        Give an Agent a role once, then use it across your graphs and chats.
                    </p>
                    <button class="text-ember-glow mt-4 text-sm font-semibold" @click="edit()">
                        Create a custom Agent →
                    </button>
                </div>
                <p v-if="store.loading" role="status">Loading Agents…</p>
                <p v-else-if="!store.items.length && !isEmptyLibrary">
                    No Agents found. Create an Agent or adjust your filters.
                </p>
                <div v-if="preview" ref="previewHost" class="scroll-mt-5">
                    <UiLibraryAgentPreview
                        :id="previewPanelId"
                        :key="preview.id"
                        :agent="preview"
                        :owned="store.library.some((item) => item.id === preview?.id)"
                        :admin="user?.is_admin"
                        :pending="actionPending"
                        :error="error || store.error"
                        @close="closePreview"
                        @edit="edit(preview)"
                        @fork="perform(() => store.fork(preview!.id))"
                        @bookmark="perform(() => store.bookmark(preview!))"
                        @rate="(rating) => perform(() => store.rate(preview!.id, rating))"
                        @verify="perform(() => store.verify(preview!.id, !preview!.verified))"
                    />
                </div>
                <div class="grid gap-4 lg:grid-cols-2">
                    <UiLibraryAgentCard
                        v-for="agent in store.items"
                        :key="agent.id"
                        :agent="agent"
                        :owned="store.library.some((item) => item.id === agent.id)"
                        :selected="preview?.id === agent.id"
                        :preview-id="previewPanelId"
                        @preview="openPreview(agent)"
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
            </template>
            <p v-if="(error || store.error) && !preview" role="alert" class="text-red-400">
                {{ error || store.error }}
            </p>
        </template>
    </section>
</template>
