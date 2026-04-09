<script lang="ts" setup>
import type {
    PromptImproverAudit,
    PromptImproverClarificationRound,
    PromptImproverRun,
} from '@/types/promptImprover';

const props = defineProps<{
    currentRun: PromptImproverRun;
    currentAudit: PromptImproverAudit | null;
    pendingClarificationRound: PromptImproverClarificationRound | null;
    answeredClarificationRounds: PromptImproverClarificationRound[];
    isAwaitingClarification: boolean;
    isQuestionSubmitting: boolean;
    canImprove: boolean;
    isImproving: boolean;
    sourcePrompt: string;
    composedPrompt: string;
    feedbackText: string;
    isFeedbackSubmitting: boolean;
    reviewStats: {
        accepted: number;
        rejected: number;
        pending: number;
        total: number;
    };
    dimensionLookup: Map<string, { label: string; category: string; tier: number }>;
    canApply: boolean;
    isApplying: boolean;
}>();

const emit = defineEmits<{
    submitClarificationAnswer: [answer: Record<string, unknown>];
    runImprove: [];
    updateFeedbackText: [value: string];
    submitFeedback: [];
    updateChangeReview: [changeId: string, reviewStatus: string];
    applyToGraph: [];
}>();

const severityClass = (severity: string) => {
    switch (severity.toLowerCase()) {
        case 'critical':
            return 'border-l-rose-400 bg-rose-500/5 text-rose-400';
        case 'high':
            return 'border-l-amber-400 bg-amber-500/5 text-amber-400';
        case 'medium':
            return 'border-l-cyan-400 bg-cyan-500/5 text-cyan-300';
        default:
            return 'border-l-deep-sea-teal bg-deep-sea-teal/5 text-deep-sea-teal';
    }
};

const severityDotClass = (severity: string) => {
    switch (severity.toLowerCase()) {
        case 'critical':
            return 'bg-rose-400';
        case 'high':
            return 'bg-amber-400';
        case 'medium':
            return 'bg-cyan-400';
        default:
            return 'bg-deep-sea-teal';
    }
};

const handleReviewChange = (changeId: string, reviewStatus: string) => {
    emit('updateChangeReview', changeId, reviewStatus);
};

const severityRank = (severity: string) => {
    switch (severity.toLowerCase()) {
        case 'critical':
            return 0;
        case 'high':
            return 1;
        case 'medium':
            return 2;
        default:
            return 3;
    }
};

const sortedDetectedIssues = computed(() => {
    const issues = props.currentAudit?.detectedIssues || [];
    return issues
        .map((issue, index) => ({ issue, index }))
        .sort((left, right) => {
            const severityDiff =
                severityRank(left.issue.severity) - severityRank(right.issue.severity);
            if (severityDiff !== 0) {
                return severityDiff;
            }

            return left.index - right.index;
        })
        .map(({ issue }) => issue);
});
</script>

<template>
    <div class="grid gap-3 xl:grid-cols-[1.1fr_1fr]">
        <div class="space-y-3">
            <div
                v-if="isAwaitingClarification"
                class="border-ember-glow/20 bg-ember-glow/5 rounded-xl border p-5"
            >
                <div class="mb-3">
                    <h3 class="text-soft-silk text-sm font-semibold">Clarification Needed</h3>
                    <p class="text-stone-gray/60 mt-1 text-xs leading-relaxed">
                        Answer the blocking questions below to continue the prompt improver.
                    </p>
                </div>
                <UiLibraryPromptImproverQuestionCard
                    v-if="pendingClarificationRound"
                    :key="pendingClarificationRound.id"
                    :round="pendingClarificationRound"
                    :is-submitting="isQuestionSubmitting"
                    class="my-3"
                    @submit="emit('submitClarificationAnswer', $event)"
                />
            </div>

            <UiLibraryPromptImproverQuestionCard
                v-for="round in answeredClarificationRounds"
                :key="round.id"
                :round="round"
                :is-submitting="false"
            />

            <div
                v-if="currentAudit"
                class="rounded-xl border border-white/5 bg-white/2 p-5"
            >
                <div class="mb-4 flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="text-soft-silk text-sm font-semibold">Detected Issues</span>
                        <span
                            v-if="sortedDetectedIssues.length"
                            class="text-stone-gray/50 rounded-full bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold tabular-nums"
                        >
                            {{ sortedDetectedIssues.length }}
                        </span>
                    </div>
                    <button
                        class="bg-ember-glow text-obsidian group hover:shadow-ember-glow/20 relative overflow-hidden rounded-lg px-4 py-2 text-xs font-bold transition-all duration-200 hover:shadow-lg disabled:opacity-40 disabled:shadow-none"
                        :disabled="!canImprove"
                        @click="emit('runImprove')"
                    >
                        <span class="relative z-10">{{ isImproving ? 'Improving…' : 'Smart Improve' }}</span>
                        <div
                            v-if="!isImproving && canImprove"
                            class="absolute inset-0 -translate-x-full bg-linear-to-r from-transparent via-white/20 to-transparent group-hover:animate-[shimmer_1.5s_ease-in-out]"
                        />
                    </button>
                </div>

                <div v-if="sortedDetectedIssues.length" class="grid gap-2 md:grid-cols-2">
                    <div
                        v-for="issue in sortedDetectedIssues"
                        :key="issue.id + issue.description"
                        class="rounded-lg border border-l-[3px] border-white/5 p-3 transition-colors duration-200"
                        :class="severityClass(issue.severity)"
                    >
                        <div class="mb-1.5 flex items-center justify-between">
                            <span class="text-soft-silk/90 text-xs font-semibold">
                                {{ issue.label }}
                            </span>
                            <span
                                class="flex items-center gap-1 rounded-full bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold tracking-wider uppercase"
                            >
                                <span class="h-1 w-1 rounded-full" :class="severityDotClass(issue.severity)" />
                                {{ issue.severity }}
                            </span>
                        </div>
                        <p class="text-stone-gray/60 text-[11px] leading-relaxed">
                            {{ issue.description }}
                        </p>
                    </div>
                </div>
                <p
                    v-else
                    class="text-stone-gray/40 rounded-lg border border-white/5 bg-emerald-500/3 px-4 py-6 text-center text-xs"
                >
                    No issues detected. This prompt looks healthy.
                </p>
            </div>

            <div class="grid gap-4 rounded-xl border border-white/5 bg-white/2 p-5 lg:grid-cols-2">
                <div>
                    <div class="mb-2 flex items-center justify-between">
                        <span class="text-soft-silk/80 text-xs font-semibold">Original</span>
                        <span
                            v-if="currentRun.sourceTemplateSnapshot"
                            class="text-stone-gray/40 text-[9px] tracking-wider uppercase"
                        >
                            Template
                        </span>
                    </div>
                    <pre
                        class="dark-scrollbar bg-anthracite/20 text-stone-gray/70 h-64 overflow-auto rounded-lg border border-white/5 p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap"
                    >{{ sourcePrompt }}</pre>
                </div>
                <div>
                    <div class="mb-2 flex items-center justify-between">
                        <span class="text-soft-silk/80 text-xs font-semibold">Composed Result</span>
                        <span
                            v-if="composedPrompt && composedPrompt !== sourcePrompt"
                            class="text-[9px] tracking-wider text-emerald-400/50 uppercase"
                        >
                            Modified
                        </span>
                    </div>
                    <pre
                        class="dark-scrollbar bg-anthracite/20 text-soft-silk/80 h-64 overflow-auto rounded-lg border border-white/5 p-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap"
                        :class="composedPrompt && composedPrompt !== sourcePrompt ? 'border-emerald-500/10' : ''"
                    >{{ composedPrompt }}</pre>
                </div>
            </div>

            <div class="rounded-xl border border-white/5 bg-white/2 p-5">
                <div class="mb-3 flex items-center justify-between">
                    <span class="text-soft-silk text-sm font-semibold">Follow-up Feedback</span>
                    <button
                        class="bg-soft-silk/8 text-soft-silk/80 hover:bg-soft-silk/12 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-200 disabled:opacity-40"
                        :disabled="!feedbackText.trim() || isFeedbackSubmitting || isAwaitingClarification"
                        @click="emit('submitFeedback')"
                    >
                        {{ isFeedbackSubmitting ? 'Re-improving…' : 'Re-improve' }}
                    </button>
                </div>
                <textarea
                    :value="feedbackText"
                    placeholder="Describe what still needs to change — e.g., handle edge cases more explicitly, reduce formality, or preserve the exact output schema…"
                    class="bg-anthracite/20 text-soft-silk/80 placeholder-stone-gray/30 h-24 w-full resize-none rounded-lg border border-white/5 p-3 text-xs transition-colors duration-200 outline-none focus:border-white/10"
                    :disabled="isAwaitingClarification"
                    @input="emit('updateFeedbackText', ($event.target as HTMLTextAreaElement).value)"
                />
            </div>
        </div>

        <div class="space-y-5">
            <UiLibraryPromptImproverReviewPanel
                :current-run="currentRun"
                :review-stats="reviewStats"
                :can-apply="canApply"
                :is-applying="isApplying"
                :dimension-lookup="dimensionLookup"
                @apply="emit('applyToGraph')"
                @update-change-review="handleReviewChange"
            />
        </div>
    </div>
</template>

<style scoped>
@keyframes shimmer {
    to {
        transform: translateX(200%);
    }
}
</style>
