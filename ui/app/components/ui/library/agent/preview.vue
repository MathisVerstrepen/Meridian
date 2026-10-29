<script setup lang="ts">
import type { AgentRecord } from '@/types/agent';
import { AGENT_TOOLS } from '@/utils/agentEditor';
const props = defineProps<{
    agent: AgentRecord;
    owned: boolean;
    admin?: boolean;
    pending?: boolean;
    error?: string;
}>();
defineEmits<{ close: []; edit: []; fork: []; bookmark: []; rate: [rating: number]; verify: [] }>();
const models = useModelStore();
const modelName = computed(
    () =>
        models.models.find((model) => model.id === props.agent.profile.model_settings.model)
            ?.name ?? props.agent.profile.model_settings.model,
);
const tools = computed(() =>
    AGENT_TOOLS.filter((tool) => props.agent.profile.tools.includes(tool.value)),
);
const heading = ref<HTMLElement | null>(null);
onMounted(() => heading.value?.focus({ preventScroll: true }));
</script>

<template>
    <section
        class="border-ember-glow/25 bg-anthracite/10 scroll-mt-5 rounded-2xl border p-5 sm:p-6"
        aria-label="Agent preview"
    >
        <div class="flex items-start gap-3">
            <span
                class="flex size-12 shrink-0 items-center justify-center rounded-xl"
                :style="{
                    color: agent.profile.accentColor,
                    backgroundColor: `${agent.profile.accentColor}1a`,
                }"
            >
                <UiIcon
                    :name="agent.profile.icon === 'LucideBot' ? 'RiBrain2Line' : agent.profile.icon"
                    class="size-7"
                />
            </span>
            <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                    <h3
                        ref="heading"
                        tabindex="-1"
                        class="rounded text-lg font-semibold wrap-break-word outline-none"
                    >
                        {{ agent.profile.name }}
                    </h3>
                    <span
                        v-if="agent.verified"
                        class="text-ember-glow inline-flex items-center gap-1 text-xs"
                        ><UiIcon
                            name="MaterialSymbolsCheckCircleOutlineRounded"
                            class="size-4"
                        />Verified by Meridian</span
                    >
                </div>
                <p class="text-stone-gray/65 mt-1 text-xs">
                    By {{ agent.author }} · Version {{ agent.version }}
                </p>
            </div>
            <button
                type="button"
                aria-label="Close Agent preview"
                class="text-stone-gray hover:bg-stone-gray/10 hover:text-soft-silk rounded-lg p-2"
                @click="$emit('close')"
            >
                <UiIcon name="MaterialSymbolsClose" class="size-5" />
            </button>
        </div>
        <p class="text-stone-gray/85 mt-4 max-w-3xl text-sm leading-relaxed wrap-break-word">
            {{ agent.profile.description || 'No description yet.' }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2 text-xs">
            <span
                class="bg-stone-gray/8 text-stone-gray inline-flex items-center gap-1.5 rounded-lg
                    px-2.5 py-1.5"
                ><UiIcon
                    :name="
                        agent.profile.visibility === 'public'
                            ? 'MdiWeb'
                            : 'MaterialSymbolsLockOutline'
                    "
                    class="size-3.5"
                />{{ agent.profile.visibility === 'public' ? 'Public' : 'Private' }}</span
            >
            <span class="bg-stone-gray/8 text-stone-gray rounded-lg px-2.5 py-1.5">{{
                agent.profile.category
            }}</span>
            <span
                v-for="tag in agent.profile.tags"
                :key="tag"
                class="text-stone-gray/70 border-stone-gray/15 rounded-lg border px-2.5 py-1.5"
                >#{{ tag }}</span
            >
        </div>
        <div class="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <section class="min-w-0 space-y-3" aria-label="Agent instructions preview">
                <h4 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                    Instructions
                </h4>
                <div class="max-h-72 space-y-4 overflow-y-auto overscroll-contain pr-2">
                    <div
                        v-for="(layer, index) in agent.profile.prompt_stack"
                        :key="index"
                        class="border-stone-gray/15 border-l-2 pl-3"
                        :class="layer.enabled ? '' : 'opacity-55'"
                    >
                        <p class="mb-1.5 text-xs font-semibold">
                            {{ layer.name
                            }}<span
                                v-if="!layer.enabled"
                                class="text-stone-gray/65 ml-2 font-normal"
                                >Disabled</span
                            >
                        </p>
                        <p
                            class="text-stone-gray/85 text-sm leading-relaxed wrap-break-word
                                whitespace-pre-wrap"
                        >
                            {{ layer.text || 'No instructions in this layer.' }}
                        </p>
                    </div>
                    <p v-if="!agent.profile.prompt_stack.length" class="text-stone-gray/65 text-sm">
                        No instruction layers.
                    </p>
                </div>
            </section>
            <div class="min-w-0 space-y-4">
                <section aria-label="Agent model preview" class="space-y-2">
                    <h4
                        class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold"
                    >
                        Model
                    </h4>
                    <p class="text-stone-gray flex items-start gap-2 text-sm wrap-break-word">
                        <UiIcon name="RiBrain2Line" class="mt-0.5 size-4 shrink-0" />{{ modelName }}
                    </p>
                </section>
                <section aria-label="Agent tools preview" class="space-y-2">
                    <h4
                        class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold"
                    >
                        Tools
                        <span class="text-stone-gray/65 ml-1 font-normal">{{ tools.length }}</span>
                    </h4>
                    <div class="flex flex-wrap gap-2">
                        <span
                            v-for="tool in tools"
                            :key="tool.value"
                            :title="tool.description"
                            class="bg-stone-gray/8 text-stone-gray inline-flex items-center gap-1.5
                                rounded-lg px-2 py-1.5 text-xs"
                            ><UiIcon :name="tool.icon" class="size-3.5" />{{ tool.name }}</span
                        >
                        <p v-if="!tools.length" class="text-stone-gray/65 text-xs">
                            Responds without external tools.
                        </p>
                    </div>
                </section>
                <p v-if="agent.source_id" class="text-stone-gray/60 text-xs">
                    Forked from source version {{ agent.source_version }}.
                </p>
            </div>
        </div>
        <div
            class="border-stone-gray/15 mt-5 flex flex-wrap items-center justify-between gap-4
                border-t pt-4"
        >
            <div class="space-y-2">
                <p class="text-stone-gray/70 flex flex-wrap items-center gap-3 text-xs">
                    <span class="inline-flex items-center gap-1"
                        ><UiIcon
                            name="MaterialSymbolsStarRounded"
                            class="text-ember-glow size-3.5"
                        />{{
                            agent.rating_count
                                ? agent.rating_average.toFixed(1) + ' / 5'
                                : 'No ratings yet'
                        }}<span v-if="agent.rating_count">({{ agent.rating_count }})</span></span
                    ><span>{{ agent.usage_count }} uses</span>
                </p>
                <div class="flex items-center gap-2" role="group" aria-label="Your rating">
                    <span class="text-stone-gray/65 text-xs">Your rating</span>
                    <button
                        v-for="rating in 5"
                        :key="rating"
                        type="button"
                        :aria-label="`Rate ${rating} of 5`"
                        :aria-pressed="agent.my_rating === rating"
                        :disabled="pending"
                        class="hover:text-ember-glow focus-visible:outline-ember-glow rounded p-1
                            transition-colors focus-visible:outline-2 disabled:opacity-40"
                        :class="
                            rating <= (agent.my_rating ?? 0)
                                ? 'text-ember-glow'
                                : 'text-stone-gray/45'
                        "
                        @click="$emit('rate', rating)"
                    >
                        <UiIcon
                            :name="
                                rating <= (agent.my_rating ?? 0)
                                    ? 'MaterialSymbolsStarRounded'
                                    : 'MaterialSymbolsStarOutlineRounded'
                            "
                            class="size-5"
                        />
                    </button>
                </div>
            </div>
            <div class="flex flex-wrap gap-2 text-sm">
                <button
                    type="button"
                    :disabled="pending"
                    :aria-pressed="agent.bookmarked"
                    class="border-stone-gray/20 text-stone-gray hover:bg-stone-gray/5 inline-flex
                        items-center gap-2 rounded-lg border px-3 py-2 disabled:opacity-40"
                    @click="$emit('bookmark')"
                >
                    <UiIcon name="MdiBookmarkOutline" class="size-4" />{{
                        agent.bookmarked ? 'Bookmarked' : 'Bookmark'
                    }}
                </button>
                <button
                    type="button"
                    :disabled="pending"
                    class="bg-ember-glow hover:bg-ember-glow/85 inline-flex items-center gap-2
                        rounded-lg px-3 py-2 font-semibold disabled:opacity-40"
                    @click="owned ? $emit('edit') : $emit('fork')"
                >
                    <UiIcon
                        :name="owned ? 'MaterialSymbolsEditRounded' : 'Fa6SolidPlus'"
                        class="size-4"
                    />{{ owned ? 'Edit Agent' : 'Add to my library' }}
                </button>
            </div>
        </div>
        <button
            v-if="admin"
            type="button"
            :disabled="pending"
            class="text-stone-gray/70 hover:text-ember-glow mt-4 inline-flex items-center gap-1.5
                text-xs disabled:opacity-40"
            @click="$emit('verify')"
        >
            <UiIcon name="MaterialSymbolsAddModeratorOutline" class="size-4" />{{
                agent.verified ? 'Remove verification' : 'Verify by Meridian'
            }}
        </button>
        <p v-if="pending" role="status" class="text-stone-gray/65 mt-3 text-xs">Updating Agent…</p>
        <p v-if="error" role="alert" class="mt-3 text-sm text-red-400">{{ error }}</p>
    </section>
</template>
