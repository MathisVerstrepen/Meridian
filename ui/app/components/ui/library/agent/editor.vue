<script setup lang="ts">
import type { AgentProfile, AgentRecord } from '@/types/agent';
import { useAgentProfileEditor } from '@/composables/useAgentProfileEditor';
const props = defineProps<{
    agent?: AgentRecord;
    preset?: AgentProfile;
    presets?: AgentProfile[];
}>();
const emit = defineEmits<{ saved: []; close: [] }>();
const {
    profile,
    instructions,
    showHandle,
    handleError,
    modelError,
    form,
    saving,
    saveIntent,
    error,
    history,
    applyPreset,
    setHandle,
    save,
    restore,
} = useAgentProfileEditor(props.agent, props.preset, () => emit('saved'));
const modelStore = useModelStore();
const modelName = computed(
    () =>
        modelStore.models.find((model) => model.id === profile.value.model_settings.model)?.name ??
        'Choose a model',
);
const displayIcon = computed(() =>
    profile.value.icon === 'LucideBot' ? 'RiBrain2Line' : profile.value.icon,
);
const inputClass =
    'bg-anthracite/25 border-stone-gray/20 focus:border-ember-glow/70 placeholder:text-stone-gray/35 text-soft-silk w-full rounded-xl border px-3.5 py-3 text-sm outline-none transition-colors';
const updateHandle = (event: Event) => {
    if (event.target instanceof HTMLInputElement) setHandle(event.target.value);
};
const dateLabel = (date: string) =>
    new Date(date).toLocaleDateString(undefined, { dateStyle: 'medium' });
</script>

<template>
    <form
        ref="form"
        class="text-soft-silk mx-auto w-full max-w-5xl"
        aria-label="Agent editor"
        @submit.prevent="save(props.agent ? null : 'active')"
    >
        <button
            type="button"
            :disabled="saving"
            class="text-stone-gray/70 hover:text-soft-silk mb-5 inline-flex items-center gap-1.5
                text-sm transition-colors disabled:opacity-40"
            @click="emit('close')"
        >
            <UiIcon name="TablerChevronCompactLeft" class="size-5" /> Agent library
        </button>
        <div class="mb-7 flex items-start justify-between gap-4">
            <div>
                <h2 class="text-2xl font-semibold tracking-tight">
                    {{ props.agent ? 'Edit Agent' : 'Create an Agent' }}
                </h2>
                <p class="text-stone-gray/70 mt-2 text-sm">
                    {{
                        props.agent
                            ? 'Refine its role and capabilities. Saving creates a new version.'
                            : 'Give it a role and choose a model. New Agents join your Default Team.'
                    }}
                </p>
            </div>
            <span
                class="border-stone-gray/15 text-stone-gray/75 shrink-0 rounded-full border px-3
                    py-1.5 text-xs"
                >{{ props.agent ? `Version ${props.agent.version}` : 'Private by default' }}</span
            >
        </div>
        <details
            v-if="!props.agent && props.presets?.length"
            class="group border-stone-gray/15 mb-6 rounded-xl border"
        >
            <summary class="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5">
                <UiIcon name="MynauiSparklesSolid" class="text-ember-glow size-5" /><span
                    class="text-stone-gray flex-1 text-sm"
                    >Get a head start with a template</span
                >
                <UiIcon
                    name="FlowbiteChevronDownOutline"
                    class="text-stone-gray/60 size-4 transition-transform group-open:rotate-180"
                />
            </summary>
            <div class="border-stone-gray/10 border-t p-3">
                <UiLibraryAgentStarterTemplates :presets="props.presets" @choose="applyPreset" />
            </div>
        </details>
        <div class="grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_16rem]">
            <div class="min-w-0 space-y-7">
                <section class="space-y-4" aria-label="Agent identity">
                    <label class="flex flex-col gap-2"
                        ><span class="text-sm font-medium"
                            >Name <span class="text-ember-glow" aria-hidden="true">*</span></span
                        >
                        <input
                            v-model="profile.name"
                            required
                            maxlength="100"
                            :class="inputClass"
                            placeholder="e.g. Web Researcher"
                            autocomplete="off"
                            autofocus
                        />
                    </label>
                    <div
                        class="text-stone-gray/60 -mt-2 flex flex-wrap items-center gap-x-2 gap-y-1
                            text-xs"
                    >
                        <span
                            >Library handle
                            <span class="text-stone-gray font-medium"
                                >@{{ profile.handle || 'your-agent' }}</span
                            ></span
                        >
                        <button
                            type="button"
                            class="text-ember-glow hover:underline"
                            :aria-expanded="showHandle"
                            @click="showHandle = !showHandle"
                        >
                            {{ showHandle ? 'Done' : 'Edit handle' }}
                        </button>
                    </div>
                    <label v-if="showHandle" class="text-stone-gray flex flex-col gap-2 text-sm"
                        >Agent handle
                        <input
                            :value="profile.handle"
                            aria-label="Agent handle"
                            :class="inputClass"
                            maxlength="50"
                            autocomplete="off"
                            :aria-invalid="!!handleError"
                            @input="updateHandle"
                        />
                        <span class="text-stone-gray/55 text-xs"
                            >Unique in your library. Lowercase letters, numbers, hyphens, and
                            underscores.</span
                        >
                    </label>
                    <p v-if="handleError" role="alert" class="text-sm text-red-400">
                        {{ handleError }}
                    </p>
                    <label class="flex flex-col gap-2"
                        ><span class="text-sm font-medium"
                            >What does it help with?
                            <span class="text-stone-gray/45 font-normal">Optional</span></span
                        >
                        <input
                            v-model="profile.description"
                            maxlength="2000"
                            :class="inputClass"
                            placeholder="A short description to recognize it in your library."
                        />
                    </label>
                </section>
                <section aria-label="Agent instructions">
                    <label class="flex flex-col gap-2"
                        ><span class="text-base font-semibold">How should it work?</span>
                        <span class="text-stone-gray/65 mb-1 text-sm"
                            >Describe its expertise, approach, and the kind of response you
                            want.</span
                        >
                        <textarea
                            v-model="instructions"
                            aria-label="Agent instructions"
                            rows="6"
                            maxlength="100000"
                            :class="inputClass"
                            placeholder="You are a web researcher. Find reliable sources, compare the evidence, and summarize the key findings. Include links and flag anything uncertain."
                        />
                    </label>
                    <p
                        v-if="profile.prompt_stack[0]?.enabled === false"
                        class="mt-2 text-xs text-amber-400"
                    >
                        This instruction layer is disabled. Enable it in Instruction layers below.
                    </p>
                </section>
                <section aria-label="Primary model">
                    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <h3 class="text-base font-semibold">Choose a model</h3>
                        <span class="text-stone-gray/55 text-xs">Search your available models</span>
                    </div>
                    <UiModelsSelect
                        :model="profile.model_settings.model"
                        :set-model="
                            (value) => {
                                profile.model_settings.model = value;
                                modelError = '';
                            }
                        "
                        :disabled="saving"
                        variant="grey"
                        to="right"
                        from="bottom"
                        class="h-12 w-full"
                        prevent-trigger-on-mount
                        :require-structured-outputs="profile.model_settings.structured_output"
                    />
                    <p v-if="modelError" role="alert" class="mt-2 text-sm text-red-400">
                        {{ modelError }}
                    </p>
                </section>
                <UiLibraryAgentToolPermissions v-model="profile.tools" />
                <section class="space-y-3" aria-label="Optional Agent settings">
                    <div>
                        <h3 class="text-sm font-semibold">Make it your own</h3>
                        <p class="text-stone-gray/55 mt-1 text-xs">Everything below is optional.</p>
                    </div>
                    <UiLibraryAgentProfileDetails v-model="profile" :editing="!!props.agent" />
                    <UiLibraryAgentPromptLayers v-model="profile.prompt_stack" />
                    <UiLibraryAgentModelOverrides v-model="profile.model_settings" />
                </section>
                <details
                    v-if="history.length"
                    class="group border-stone-gray/15 rounded-xl border p-4"
                >
                    <summary class="text-stone-gray cursor-pointer text-sm">
                        Version history · {{ history.length }} saved versions
                    </summary>
                    <div
                        v-for="version in history"
                        :key="version.version"
                        class="border-stone-gray/10 mt-3 flex flex-wrap items-center justify-between
                            gap-2 border-t pt-3 text-sm"
                    >
                        <span class="text-stone-gray/70"
                            >v{{ version.version }} · {{ dateLabel(version.created_at) }}</span
                        >
                        <button
                            type="button"
                            :disabled="saving"
                            class="text-ember-glow disabled:opacity-40"
                            @click="restore(version.version)"
                        >
                            Restore as new version
                        </button>
                    </div>
                </details>
            </div>
            <aside
                class="border-stone-gray/15 bg-anthracite/10 sticky top-5 hidden rounded-2xl border
                    p-5 xl:block"
                aria-label="Agent preview"
            >
                <p class="text-stone-gray/45 mb-5 text-xs font-medium tracking-wider uppercase">
                    Your Agent
                </p>
                <div
                    class="mb-4 flex size-12 items-center justify-center rounded-2xl"
                    :style="{
                        color: profile.accentColor,
                        backgroundColor: `${profile.accentColor}1a`,
                    }"
                >
                    <UiIcon :name="displayIcon" class="size-7" />
                </div>
                <h3 class="font-semibold wrap-break-word">
                    {{ profile.name || 'Your new Agent' }}
                </h3>
                <p class="text-stone-gray/50 mt-1 text-xs wrap-break-word">
                    @{{ profile.handle || 'your-agent' }}
                </p>
                <p class="text-stone-gray/70 mt-4 text-sm leading-relaxed wrap-break-word">
                    {{ profile.description || 'A dedicated helper for the way you work.' }}
                </p>
                <div class="border-stone-gray/10 mt-5 space-y-3 border-t pt-4 text-xs">
                    <div>
                        <span class="text-stone-gray/45 block">Model</span
                        ><span class="text-stone-gray mt-1 block wrap-break-word">{{
                            modelName
                        }}</span>
                    </div>
                    <p class="text-stone-gray/70">
                        {{
                            profile.tools.length
                                ? `${profile.tools.length} tools enabled`
                                : 'Responds without external tools'
                        }}
                    </p>
                    <p class="text-stone-gray/55">
                        {{
                            profile.visibility === 'private'
                                ? 'Only you can access this Agent.'
                                : 'Visible in the Agent marketplace.'
                        }}
                    </p>
                </div>
                <p class="text-stone-gray/50 mt-5 text-xs leading-relaxed">
                    Available through your Default Team. Add it to other Teams in your library.
                </p>
            </aside>
        </div>
        <footer
            class="bg-obsidian/95 border-stone-gray/15 sticky -bottom-1 z-10 mt-8 flex flex-wrap
                items-center justify-between gap-3 border-t py-4 backdrop-blur-xl"
        >
            <p v-if="error" role="alert" class="w-full text-sm text-red-400">{{ error }}</p>
            <span class="text-stone-gray/60 text-xs"
                >{{
                    profile.visibility === 'private'
                        ? 'Private to your library'
                        : 'Shared in the marketplace'
                }}
                · {{ props.agent ? 'Saves a new version' : 'Ready to use after creation' }}</span
            >
            <div class="ml-auto flex items-center gap-3">
                <button
                    v-if="!props.agent"
                    type="button"
                    :disabled="saving"
                    class="text-stone-gray hover:text-soft-silk rounded-xl px-3 py-2.5 text-sm
                        transition-colors disabled:opacity-40"
                    @click="save('draft')"
                >
                    {{ saving && saveIntent === 'draft' ? 'Saving draft…' : 'Save draft' }}
                </button>
                <button
                    type="submit"
                    :disabled="saving"
                    class="bg-ember-glow hover:bg-ember-glow/85 flex items-center gap-2 rounded-xl
                        px-5 py-2.5 text-sm font-semibold transition-colors disabled:cursor-wait
                        disabled:opacity-50"
                >
                    <UiIcon
                        :name="saving ? 'MynauiSparklesSolid' : 'MaterialSymbolsCheckSmallRounded'"
                        class="size-5"
                        :class="saving ? 'animate-pulse' : ''"
                    />
                    {{
                        saving && saveIntent !== 'draft'
                            ? 'Saving…'
                            : props.agent
                              ? 'Save changes'
                              : 'Create Agent'
                    }}
                </button>
            </div>
        </footer>
    </form>
</template>
