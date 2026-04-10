<script lang="ts" setup>
import type {
    PromptImproverAudit,
    PromptImproverCategory,
    PromptImproverRun,
    PromptImproverTarget,
} from '@/types/promptImprover';
import type { NodeTypeEnum } from '@/types/enums';

const props = defineProps<{
    currentRun: PromptImproverRun | null;
    currentAudit: PromptImproverAudit | null;
    hasHistory: boolean;
    targets: PromptImproverTarget[];
    selectedTargetId: string | null;
    selectedOptimizerModelId: string | null;
    selectedTarget: PromptImproverTarget | null;
    canLaunchAnalysis: boolean;
    isBootstrapping: boolean;
    groupedCategories: PromptImproverCategory[];
    selectedDimensionIds: string[];
    historyRuns: PromptImproverRun[];
}>();

const emit = defineEmits<{
    selectTarget: [targetId: string];
    selectOptimizerModel: [modelId: string];
    launchAnalysis: [];
    toggleDimension: [dimensionId: string];
    useRecommended: [];
    selectRun: [run: PromptImproverRun];
}>();

const { getBlockByNodeType } = useBlocks();
const modelStore = useModelStore();
const { getModel } = modelStore;
const isSummaryExpanded = ref(false);

const GAUGE_CIRCUMFERENCE = 251.33;

const healthGaugeOffset = computed(() => {
    const score = props.currentAudit?.healthScore ?? 0;
    return GAUGE_CIRCUMFERENCE - (score / 100) * GAUGE_CIRCUMFERENCE;
});

const healthGaugeColor = computed(() => {
    const score = props.currentAudit?.healthScore ?? 0;
    if (score >= 80) return '#6ee7b7';
    if (score >= 60) return '#fcd34d';
    return '#fda4af';
});

const healthGlowClass = computed(() => {
    const score = props.currentAudit?.healthScore ?? 0;
    if (score >= 80) return 'bg-emerald-500/15';
    if (score >= 60) return 'bg-amber-500/15';
    return 'bg-rose-500/15';
});

const getTargetBlockIcon = (target: PromptImproverTarget) => {
    const block = getBlockByNodeType(target.nodeType as NodeTypeEnum);
    return block?.icon || 'MaterialSymbolsSmartToyRounded';
};

const getTargetModelIcon = (target: PromptImproverTarget) => {
    if (!target.modelId) {
        return null;
    }

    return getModel(target.modelId)?.icon || null;
};

const getRunDisplayName = (run: PromptImproverRun) => {
    return run.optimizerModelName || run.target.modelName || run.target.label;
};

const getTargetShortId = (target: PromptImproverTarget) => {
    const id = target.nodeId || target.id;
    if (id.length <= 8) {
        return id;
    }

    return id.slice(0, 8) + '...' + id.slice(-4);
};

const formatDate = (value: string) => {
    return new Date(value).toLocaleString();
};

const dimensionScoreLookup = computed(() => {
    const lookup = new Map<string, string>();
    for (const score of props.currentAudit?.dimensionScores || []) {
        lookup.set(score.dimensionId, score.score);
    }
    return lookup;
});

const getDimensionScoreClass = (score: string | undefined) => {
    switch (score) {
        case 'missing':
            return 'border border-rose-500/10 bg-rose-500/4 text-rose-200/65';
        case 'weak':
            return 'border border-amber-500/10 bg-amber-500/4 text-amber-200/65';
        case 'adequate':
            return 'border border-cyan-500/10 bg-cyan-500/4 text-cyan-200/65';
        case 'strong':
            return 'border border-emerald-500/10 bg-emerald-500/4 text-emerald-200/65';
        case 'excellent':
            return 'border border-fuchsia-500/10 bg-fuchsia-500/4 text-fuchsia-200/65';
        default:
            return 'border border-white/5 bg-white/2 text-stone-gray/40';
    }
};

const formatDimensionScoreLabel = (score: string | undefined) => {
    if (!score) {
        return 'Unscored';
    }

    return score.charAt(0).toUpperCase() + score.slice(1);
};

const shouldShowSummaryToggle = computed(() => {
    const summary = props.currentAudit?.summary?.trim() || '';
    return summary.length > 100;
});

const selectedOptimizerToolsSupport = computed(() => {
    if (!props.selectedOptimizerModelId) {
        return props.selectedTarget?.toolsSupport ?? false;
    }

    return !!getModel(props.selectedOptimizerModelId)?.toolsSupport;
});

watch(
    () => props.currentRun?.id,
    () => {
        isSummaryExpanded.value = false;
    },
);
</script>

<template>
    <aside
        class="border-stone-gray/10 hide-scrollbar flex min-h-0 flex-col gap-3
            overflow-y-auto border-r bg-black/20 p-4"
    >
        <div class="rounded-xl border border-white/5 bg-white/3 p-4">
            <div v-if="currentRun && currentAudit" class="flex items-start gap-4">
                <div class="relative shrink-0">
                    <div
                        class="absolute -inset-2 rounded-full blur-xl transition-colors
                            duration-700"
                        :class="healthGlowClass"
                    />
                    <svg class="gauge-svg relative h-[72px] w-[72px]" viewBox="0 0 96 96">
                        <circle
                            cx="48"
                            cy="48"
                            r="40"
                            fill="none"
                            stroke="currentColor"
                            class="text-white/5"
                            stroke-width="5"
                        />
                        <circle
                            cx="48"
                            cy="48"
                            r="40"
                            fill="none"
                            :stroke="healthGaugeColor"
                            stroke-width="5"
                            stroke-linecap="round"
                            :stroke-dasharray="GAUGE_CIRCUMFERENCE"
                            :stroke-dashoffset="healthGaugeOffset"
                            class="gauge-ring"
                            transform="rotate(-90 48 48)"
                        />
                        <text
                            x="48"
                            y="45"
                            text-anchor="middle"
                            dominant-baseline="central"
                            class="fill-soft-silk font-bold"
                            font-size="22"
                            font-family="Outfit-Variable, sans-serif"
                        >
                            {{ currentAudit.healthScore }}
                        </text>
                        <text
                            x="48"
                            y="62"
                            text-anchor="middle"
                            dominant-baseline="central"
                            class="fill-stone-gray"
                            font-size="9"
                            opacity="0.5"
                            font-family="Outfit-Variable, sans-serif"
                        >
                            / 100
                        </text>
                    </svg>
                </div>
                <div class="min-w-0 flex-1 pt-0.5">
                    <div class="mb-1.5 flex items-center gap-2">
                        <span class="text-soft-silk text-xs font-semibold">Health</span>
                        <span
                            class="text-stone-gray/60 rounded-full bg-white/5 px-1.5 py-0.5
                                text-[9px] font-semibold tracking-wider uppercase"
                        >
                            {{ currentRun.status }}
                        </span>
                    </div>
                    <p
                        class="text-stone-gray/60 text-[11px] leading-relaxed"
                        :class="{ 'line-clamp-3': !isSummaryExpanded }"
                    >
                        {{ currentAudit.summary }}
                    </p>
                    <button
                        v-if="shouldShowSummaryToggle"
                        type="button"
                        class="text-stone-gray/55 hover:text-soft-silk mt-1 text-[10px] font-medium
                            transition-colors"
                        @click="isSummaryExpanded = !isSummaryExpanded"
                    >
                        {{ isSummaryExpanded ? 'Show less' : 'Show more' }}
                    </button>
                </div>
            </div>
            <div v-else class="flex flex-col items-center gap-2 py-3">
                <svg class="h-16 w-16 text-white/5" viewBox="0 0 96 96">
                    <circle
                        cx="48"
                        cy="48"
                        r="40"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="5"
                        stroke-dasharray="4 8"
                    />
                    <text
                        x="48"
                        y="48"
                        text-anchor="middle"
                        dominant-baseline="central"
                        fill="currentColor"
                        font-size="14"
                        class="text-stone-gray/30"
                        font-family="Outfit-Variable, sans-serif"
                    >
                        —
                    </text>
                </svg>
                <p class="text-stone-gray/40 text-[11px]">Awaiting analysis</p>
            </div>
        </div>

        <div class="rounded-xl border border-white/5 bg-white/3 p-4">
            <div class="mb-3 flex items-center justify-between">
                <span class="text-soft-silk text-xs font-semibold">Analysis</span>
                <span class="text-ember-glow/70 text-[9px] font-semibold tracking-wider uppercase">
                    Manual
                </span>
            </div>
            <p class="text-stone-gray/50 mb-3 text-[11px] leading-relaxed">
                {{
                    hasHistory
                        ? 'Launch a fresh audit for the selected downstream target or inspect a previous run below.'
                        : 'No analysis has been run for this prompt yet. Launch one when you are ready.'
                }}
            </p>
            <div class="mb-3">
                <p
                    class="text-stone-gray/45 mb-1.5 text-[9px] font-bold tracking-[0.2em]
                        uppercase"
                >
                    Improver Model
                </p>
                <UiModelsSelect
                    :model="selectedOptimizerModelId || ''"
                    :set-model="(model: string) => emit('selectOptimizerModel', model)"
                    :disabled="isBootstrapping"
                    to="left"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-full"
                    teleport
                    require-structured-outputs
                    hide-tool
                />
            </div>
            <div v-if="targets.length > 1" class="space-y-1.5">
                <button
                    v-for="target in targets"
                    :key="target.id"
                    :title="target.label"
                    class="w-full rounded-lg border px-3 py-2 text-left transition-all duration-200"
                    :class="
                        selectedTargetId === target.id
                            ? `border-ember-glow/50 bg-ember-glow/8 text-soft-silk
                                shadow-ember-glow/10 shadow-[inset_0_0_12px_-4px]`
                            : `text-stone-gray/70 hover:text-soft-silk border-white/5
                                hover:border-white/10`
                    "
                    @click="emit('selectTarget', target.id)"
                >
                    <div class="flex items-center gap-2">
                        <UiIcon :name="getTargetBlockIcon(target)" class="h-4 w-4 shrink-0" />
                        <span class="truncate text-[11px] font-semibold tracking-wide">
                            {{ getTargetShortId(target) }}
                        </span>
                    </div>
                    <div class="text-stone-gray/60 mt-1 flex items-center gap-2">
                        <UiIcon
                            v-if="getTargetModelIcon(target)"
                            :name="'models/' + getTargetModelIcon(target)"
                            class="h-4 w-4 shrink-0"
                        />
                        <span v-else class="bg-stone-gray/15 h-4 w-4 shrink-0 rounded-full" />
                        <span class="truncate text-[11px] font-medium">
                            {{ target.modelId || 'No model configured' }}
                        </span>
                    </div>
                </button>
            </div>
            <div
                v-else-if="targets[0]"
                :title="targets[0].label"
                class="rounded-lg border border-white/5 bg-black/10 px-3 py-2"
            >
                <div class="flex items-center gap-2">
                    <UiIcon
                        :name="getTargetBlockIcon(targets[0])"
                        class="text-soft-silk/80 h-4 w-4 shrink-0"
                    />
                    <span
                        class="text-soft-silk/80 truncate text-[11px] font-semibold tracking-wide"
                    >
                        {{ getTargetShortId(targets[0]) }}
                    </span>
                </div>
                <div class="text-stone-gray/60 mt-1 flex items-center gap-2">
                    <UiIcon
                        v-if="getTargetModelIcon(targets[0])"
                        :name="'models/' + getTargetModelIcon(targets[0])"
                        class="h-4 w-4 shrink-0"
                    />
                    <span v-else class="bg-stone-gray/15 h-4 w-4 shrink-0 rounded-full" />
                    <span class="truncate text-[11px] font-medium">
                        {{ targets[0].modelId || 'No model configured' }}
                    </span>
                </div>
            </div>
            <button
                class="bg-ember-glow text-obsidian mt-3 w-full rounded-lg px-3 py-2 text-xs
                    font-bold transition-all duration-200 hover:brightness-110 disabled:opacity-40"
                :disabled="!canLaunchAnalysis"
                @click="emit('launchAnalysis')"
            >
                {{
                    isBootstrapping
                        ? 'Analyzing…'
                        : hasHistory
                          ? 'Run New Analysis'
                          : 'Launch Analysis'
                }}
            </button>
            <p
                v-if="selectedOptimizerModelId && !selectedOptimizerToolsSupport"
                class="text-stone-gray/45 mt-2 text-[10px] leading-relaxed"
            >
                Clarifying questions are unavailable for the selected improver model.
            </p>
        </div>

        <div
            v-if="currentRun && currentAudit"
            class="rounded-xl border border-white/5 bg-white/3 p-4"
        >
            <div class="mb-3 flex items-center justify-between">
                <span class="text-soft-silk text-xs font-semibold">Dimensions</span>
                <button
                    class="text-ember-glow/80 hover:text-ember-glow text-[8px] font-semibold
                        tracking-wider uppercase transition-colors"
                    @click="emit('useRecommended')"
                >
                    Use Recommended
                </button>
            </div>

            <div class="space-y-3">
                <div v-for="category in groupedCategories" :key="category.id" class="space-y-1.5">
                    <p class="text-stone-gray/40 text-[9px] font-bold tracking-[0.2em] uppercase">
                        {{ category.label }}
                    </p>
                    <label
                        v-for="dimension in category.dimensions"
                        :key="dimension.id"
                        class="group flex cursor-pointer items-center gap-2.5 rounded-lg border
                            border-transparent px-1 py-2 transition-all duration-150
                            hover:border-white/5 hover:bg-white/3"
                        :class="
                            selectedDimensionIds.includes(dimension.id)
                                ? 'border-white/5 bg-white/3'
                                : ''
                        "
                    >
                        <UiSettingsUtilsCheckbox
                            :model-value="selectedDimensionIds.includes(dimension.id)"
                            :style="'dark'"
                            class="scale-75"
                            label=""
                            @update:model-value="emit('toggleDimension', dimension.id)"
                        />
                        <div class="min-w-0 flex-1">
                            <div class="flex items-center gap-1.5">
                                <span class="text-soft-silk/90 text-[11px] font-medium">
                                    {{ dimension.label }}
                                </span>
                                <span
                                    class="rounded-md px-1.5 py-px text-[7px] font-medium
                                        tracking-[0.12em] uppercase"
                                    :class="
                                        getDimensionScoreClass(
                                            dimensionScoreLookup.get(dimension.id),
                                        )
                                    "
                                >
                                    {{
                                        formatDimensionScoreLabel(
                                            dimensionScoreLookup.get(dimension.id),
                                        )
                                    }}
                                </span>
                                <span
                                    v-if="currentRun.recommendedDimensionIds.includes(dimension.id)"
                                    class="border-ember-glow/12 bg-ember-glow/4
                                        text-ember-glow/60 rounded-md border px-1.5 py-px text-[7px]
                                        font-medium tracking-[0.12em] uppercase"
                                >
                                    Rec
                                </span>
                            </div>
                            <div class="text-stone-gray/40 text-[10px] leading-relaxed">
                                {{ dimension.description }}
                            </div>
                        </div>
                    </label>
                </div>
            </div>
        </div>

        <div class="rounded-xl border border-white/5 bg-white/3 p-4">
            <div class="mb-3 flex items-center justify-between">
                <span class="text-soft-silk text-xs font-semibold">History</span>
                <span class="text-stone-gray/40 text-[9px] tracking-wider uppercase">
                    {{ historyRuns.length }} run{{ historyRuns.length === 1 ? '' : 's' }}
                </span>
            </div>
            <div v-if="historyRuns.length" class="space-y-1.5">
                <button
                    v-for="run in historyRuns"
                    :key="run.id"
                    class="w-full rounded-lg border px-3 py-2 text-left transition-all duration-200"
                    :class="
                        currentRun?.id === run.id
                            ? `border-ember-glow/50 bg-ember-glow/8 shadow-ember-glow/10
                                shadow-[inset_0_0_12px_-4px]`
                            : 'border-white/5 hover:border-white/10'
                    "
                    @click="emit('selectRun', run)"
                >
                    <div class="flex items-center justify-between gap-2">
                        <span class="text-soft-silk/80 truncate text-[11px] font-medium">
                            {{ getRunDisplayName(run) }}
                        </span>
                        <span
                            class="shrink-0 text-[10px] font-bold tabular-nums"
                            :class="
                                run.audit
                                    ? run.audit.healthScore >= 80
                                        ? 'text-emerald-400/70'
                                        : run.audit.healthScore >= 60
                                          ? 'text-amber-400/70'
                                          : 'text-rose-400/70'
                                    : 'text-stone-gray/45'
                            "
                        >
                            {{ run.audit ? run.audit.healthScore : run.status }}
                        </span>
                    </div>
                    <span class="text-stone-gray/40 text-[10px]">
                        {{ formatDate(run.createdAt) }}
                    </span>
                </button>
            </div>
            <p v-else class="text-stone-gray/30 py-2 text-center text-[11px]">No previous runs</p>
        </div>
    </aside>
</template>

<style scoped>
.gauge-ring {
    transition: stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1);
}

.gauge-svg {
    filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.03));
}
</style>
