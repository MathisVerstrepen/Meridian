<script setup lang="ts">
import type { AgentRecord } from '@/types/agent';
import { useAgentProfileEditor } from '@/composables/useAgentProfileEditor';
const props = defineProps<{
    agent?: AgentRecord;
}>();
const emit = defineEmits<{ saved: []; close: [] }>();
const {
    profile,
    instructions,
    modelError,
    form,
    saving,
    saveIntent,
    error,
    history,
    save,
    restore,
} = useAgentProfileEditor(props.agent, () => emit('saved'));
const descriptionId = `agent-description-${useId()}`;
const modelStore = useModelStore();
const modelName = computed(
    () =>
        modelStore.models.find((model) => model.id === profile.value.model_settings.model)?.name ??
        'Choose a model',
);
const generatingIcon = ref(false);
const inputClass =
    'bg-anthracite/25 border-stone-gray/20 focus:border-ember-glow/70 placeholder:text-stone-gray/35 text-soft-silk w-full rounded-xl border px-3.5 py-3 text-sm outline-none transition-colors';
const { generatingDescription, descriptionError, generateDescription } = useAgentDescription(
    profile,
    instructions,
);
const dateLabel = (date: string) =>
    new Date(date).toLocaleDateString(undefined, { dateStyle: 'medium' });
</script>

<template>
    <form
        ref="form"
        class="text-soft-silk mx-auto w-full max-w-5xl pb-4"
        aria-label="Agent editor"
        @submit.prevent="
            !generatingDescription && !generatingIcon && save(props.agent ? null : 'active')
        "
    >
        <button
            type="button"
            :disabled="saving || generatingDescription || generatingIcon"
            class="text-stone-gray/70 hover:text-soft-silk mb-5 inline-flex items-center gap-1.5
                text-sm transition-colors disabled:opacity-40"
            @click="emit('close')"
        >
            <UiIcon name="MdiArrowUp" class="size-5 -rotate-90" /> Agent library
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
                    <div class="flex flex-col gap-2">
                        <label :for="descriptionId" class="text-sm font-medium"
                            >What does it help with?
                            <span class="text-stone-gray/45 font-normal">Optional</span></label
                        >
                        <span class="relative block">
                            <input
                                v-model="profile.description"
                                :id="descriptionId"
                                maxlength="2000"
                                :class="[inputClass, instructions.trim() ? 'pr-12' : '']"
                                placeholder="A short description to recognize it in your library."
                            />
                            <button
                                v-if="instructions.trim()"
                                type="button"
                                aria-label="Generate Agent description"
                                title="Generate a description from the instructions"
                                :disabled="
                                    generatingDescription ||
                                    generatingIcon ||
                                    saving ||
                                    !profile.model_settings.model
                                "
                                class="text-ember-glow hover:bg-ember-glow/10 absolute top-1/2
                                    right-2 flex size-8 -translate-y-1/2 items-center justify-center
                                    rounded-lg disabled:opacity-40"
                                @click="generateDescription"
                            >
                                <UiIcon
                                    :name="
                                        generatingDescription
                                            ? 'LineMdLoadingTwotoneLoop'
                                            : 'MynauiSparklesSolid'
                                    "
                                    class="size-5"
                                />
                            </button>
                        </span>
                    </div>
                    <p
                        v-if="generatingDescription"
                        role="status"
                        class="text-stone-gray/65 text-xs"
                    >
                        Generating description…
                    </p>
                    <p v-if="descriptionError" role="alert" class="text-xs text-red-400">
                        {{ descriptionError }}
                    </p>
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
                        :disabled="saving || generatingDescription || generatingIcon"
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
                    <UiLibraryAgentProfileDetails
                        v-model="profile"
                        :editing="!!props.agent"
                        :disabled="saving || generatingDescription"
                        @icon-busy="generatingIcon = $event"
                    />
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
                            :disabled="saving || generatingDescription || generatingIcon"
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
                <div class="mb-5 flex flex-wrap items-center justify-between gap-2">
                    <p class="text-stone-gray/45 text-xs font-medium tracking-wider uppercase">
                        Your Agent
                    </p>
                    <span
                        class="border-stone-gray/15 bg-stone-gray/5 text-stone-gray inline-flex
                            items-center gap-1.5 rounded-full border px-2 py-1 text-xs"
                        :aria-label="`Agent visibility: ${profile.visibility === 'private' ? 'Private' : 'Public'}`"
                    >
                        <UiIcon
                            :name="
                                profile.visibility === 'private'
                                    ? 'MaterialSymbolsLockOutline'
                                    : 'MdiWeb'
                            "
                            class="size-3.5"
                        />
                        {{ profile.visibility === 'private' ? 'Private' : 'Public' }}
                    </span>
                </div>
                <div
                    class="mb-4 flex size-12 items-center justify-center rounded-2xl"
                    :style="{
                        color: profile.accentColor,
                        backgroundColor: `${profile.accentColor}1a`,
                    }"
                >
                    <UiLibraryAgentIcon :profile="profile" class="size-7" />
                </div>
                <h3 class="font-semibold wrap-break-word">
                    {{ profile.name || 'Your new Agent' }}
                </h3>

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
                </div>
            </aside>
        </div>
        <footer
            aria-label="Agent save actions"
            class="bg-anthracite border-stone-gray/20 sticky bottom-3 z-10 mt-8 flex flex-wrap
                items-center justify-between gap-3 rounded-2xl border px-4 py-3 shadow-xl"
        >
            <p
                v-if="error"
                role="alert"
                class="w-full rounded-lg bg-red-400/5 px-3 py-2 text-sm text-red-400"
            >
                {{ error }}
            </p>
            <p class="text-stone-gray/80 flex items-center gap-2 text-xs" role="status">
                <UiIcon
                    :name="props.agent ? 'MaterialSymbolsHistory' : 'RiBrain2Line'"
                    class="size-4 shrink-0"
                />
                {{
                    generatingIcon
                        ? 'Generating icon…'
                        : generatingDescription
                          ? 'Generating description…'
                          : saving
                            ? 'Saving your Agent…'
                            : props.agent
                              ? `Editing v${props.agent.version} · Saves a new version`
                              : 'Ready to use after creation'
                }}
            </p>
            <div
                class="grid w-full grid-cols-[auto_minmax(0,1fr)] items-center gap-2 sm:ml-auto
                    sm:flex sm:w-auto"
            >
                <button
                    v-if="props.agent"
                    type="button"
                    :disabled="saving || generatingDescription || generatingIcon"
                    class="text-stone-gray hover:text-soft-silk border-stone-gray/20
                        hover:bg-stone-gray/5 rounded-xl border px-4 py-2.5 text-sm
                        transition-colors disabled:opacity-40"
                    @click="emit('close')"
                >
                    Cancel
                </button>
                <button
                    v-if="!props.agent"
                    type="button"
                    :disabled="saving || generatingDescription || generatingIcon"
                    class="text-stone-gray hover:text-soft-silk rounded-xl px-3 py-2.5 text-sm
                        transition-colors disabled:opacity-40"
                    @click="save('draft')"
                >
                    {{ saving && saveIntent === 'draft' ? 'Saving draft…' : 'Save draft' }}
                </button>
                <button
                    type="submit"
                    :disabled="saving || generatingDescription || generatingIcon"
                    class="bg-ember-glow hover:bg-ember-glow/85 focus-visible:outline-ember-glow
                        flex min-w-36 items-center justify-center gap-2 rounded-xl px-5 py-2.5
                        text-sm font-semibold transition-colors focus-visible:outline-2
                        focus-visible:outline-offset-2 disabled:cursor-wait disabled:opacity-50"
                >
                    <UiIcon
                        :name="
                            saving ? 'LineMdLoadingTwotoneLoop' : 'MaterialSymbolsCheckSmallRounded'
                        "
                        class="size-5"
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
