<script lang="ts" setup>
import type {
    PromptImproverAudit,
    PromptImproverClarificationRound,
    PromptImproverRun,
} from '@/types/promptImprover';

defineProps<{
    isBootstrapping: boolean;
    localError: string | null;
    currentRun: PromptImproverRun | null;
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
    canLaunchAnalysis: boolean;
}>();

const emit = defineEmits<{
    launchAnalysis: [];
    submitClarificationAnswer: [answer: Record<string, unknown>];
    runImprove: [];
    updateFeedbackText: [value: string];
    submitFeedback: [];
    updateChangeReview: [changeId: string, reviewStatus: string];
    applyToGraph: [];
}>();

const handleReviewChange = (changeId: string, reviewStatus: string) => {
    emit('updateChangeReview', changeId, reviewStatus);
};
</script>

<template>
    <section class="dark-scrollbar min-h-0 overflow-y-auto">
        <div v-if="isBootstrapping" class="flex h-full flex-col gap-6 p-6">
            <div class="animate-pulse space-y-5">
                <div class="flex items-center gap-3">
                    <div class="h-5 w-36 rounded-lg bg-white/5" />
                    <div class="h-5 w-20 rounded-lg bg-white/3" />
                </div>
                <div class="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
                    <div class="space-y-4">
                        <div class="grid grid-cols-2 gap-3">
                            <div class="h-28 rounded-xl bg-white/4" />
                            <div class="h-28 rounded-xl bg-white/3" />
                            <div class="h-28 rounded-xl bg-white/3" />
                            <div class="h-28 rounded-xl bg-white/4" />
                        </div>
                        <div class="h-72 rounded-xl bg-white/3" />
                    </div>
                    <div class="space-y-3">
                        <div class="h-48 rounded-xl bg-white/4" />
                        <div class="h-48 rounded-xl bg-white/3" />
                        <div class="h-36 rounded-xl bg-white/4" />
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="space-y-5 p-4">
            <div
                v-if="localError"
                class="flex items-start gap-3 rounded-xl border border-rose-500/20 bg-rose-500/5 p-4"
            >
                <div class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
                <p class="text-xs leading-relaxed text-rose-200/90">{{ localError }}</p>
            </div>

            <UiLibraryPromptImproverActiveRun
                v-if="currentRun"
                :current-run="currentRun"
                :current-audit="currentAudit"
                :pending-clarification-round="pendingClarificationRound"
                :answered-clarification-rounds="answeredClarificationRounds"
                :is-awaiting-clarification="isAwaitingClarification"
                :is-question-submitting="isQuestionSubmitting"
                :can-improve="canImprove"
                :is-improving="isImproving"
                :source-prompt="sourcePrompt"
                :composed-prompt="composedPrompt"
                :feedback-text="feedbackText"
                :is-feedback-submitting="isFeedbackSubmitting"
                :review-stats="reviewStats"
                :dimension-lookup="dimensionLookup"
                :can-apply="canApply"
                :is-applying="isApplying"
                @submit-clarification-answer="emit('submitClarificationAnswer', $event)"
                @run-improve="emit('runImprove')"
                @update-feedback-text="emit('updateFeedbackText', $event)"
                @submit-feedback="emit('submitFeedback')"
                @update-change-review="handleReviewChange"
                @apply-to-graph="emit('applyToGraph')"
            />

            <div v-else class="flex h-[60vh] flex-col items-center justify-center gap-5">
                <div class="relative">
                    <div class="bg-ember-glow/8 absolute -inset-6 rounded-full blur-2xl" />
                    <UiIcon
                        name="MynauiSparklesSolid"
                        class="text-ember-glow/40 relative h-14 w-14"
                    />
                </div>
                <div class="text-center">
                    <p class="text-soft-silk/70 text-sm font-semibold">Ready to analyze</p>
                    <p class="text-stone-gray/40 mx-auto mt-1.5 max-w-xs text-xs leading-relaxed">
                        Select a downstream target, adjust the improver model if needed, and start
                        the audit to see prompt health analysis and improvement recommendations.
                    </p>
                    <button
                        class="bg-ember-glow text-obsidian mt-6 rounded-xl px-5 py-3 text-sm font-bold transition-all duration-200 hover:brightness-110 disabled:opacity-40"
                        :disabled="!canLaunchAnalysis"
                        @click="emit('launchAnalysis')"
                    >
                        {{ isBootstrapping ? 'Analyzing…' : 'Launch Analysis' }}
                    </button>
                </div>
            </div>
        </div>
    </section>
</template>
