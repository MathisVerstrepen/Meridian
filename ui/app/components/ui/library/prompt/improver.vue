<script lang="ts" setup>
import { motion } from 'motion-v';

const {
    isOpen,
    isBootstrapping,
    isImproving,
    isApplying,
    isFeedbackSubmitting,
    isQuestionSubmitting,
    targets,
    selectedTargetId,
    currentRun,
    historyRuns,
    feedbackText,
    localError,
    selectedDimensionIds,
    currentAudit,
    selectedTarget,
    pendingClarificationRound,
    answeredClarificationRounds,
    isAwaitingClarification,
    reviewStats,
    workflowStep,
    workflowSteps,
    groupedCategories,
    dimensionLookup,
    canImprove,
    canApply,
    hasHistory,
    canLaunchAnalysis,
    composedPrompt,
    sourcePrompt,
    close,
    launchAnalysis,
    toggleDimension,
    useRecommendedDimensions,
    runImprove,
    updateChangeReview,
    submitFeedback,
    submitClarificationAnswer,
    applyToGraph,
    setCurrentRun,
} = usePromptImprover();

const handleChangeReview = (changeId: string, reviewStatus: string) => {
    updateChangeReview(changeId, reviewStatus);
};
</script>

<template>
    <Teleport to="body">
        <AnimatePresence>
            <motion.div
                v-if="isOpen"
                key="prompt-improver"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1, transition: { duration: 0.2 } }"
                :exit="{ opacity: 0, transition: { duration: 0.2 } }"
                class="bg-anthracite/40 fixed inset-0 z-35 flex items-center justify-center p-4
                    backdrop-blur-md sm:p-6"
                @click.self="close"
            >
                <motion.div
                    :initial="{ opacity: 0, scale: 0.96, y: 10 }"
                    :animate="{
                        opacity: 1,
                        scale: 1,
                        y: 0,
                        transition: { duration: 0.25, ease: 'easeOut' },
                    }"
                    :exit="{
                        opacity: 0,
                        scale: 0.96,
                        y: 10,
                        transition: { duration: 0.18, ease: 'easeIn' },
                    }"
                    class="bg-obsidian/95 border-stone-gray/10 grid h-[92vh] w-full max-w-400
                        grid-rows-[auto_1fr] overflow-hidden rounded-2xl border shadow-2xl"
                >
                    <UiLibraryPromptImproverHeader
                        :current-run="currentRun"
                        :workflow-step="workflowStep"
                        :workflow-steps="workflowSteps"
                        @close="close"
                    />

                    <div class="grid min-h-0 grid-cols-[300px_1fr]">
                        <UiLibraryPromptImproverSidebar
                            :current-run="currentRun"
                            :current-audit="currentAudit"
                            :has-history="hasHistory"
                            :targets="targets"
                            :selected-target-id="selectedTargetId"
                            :selected-target="selectedTarget"
                            :can-launch-analysis="canLaunchAnalysis"
                            :is-bootstrapping="isBootstrapping"
                            :grouped-categories="groupedCategories"
                            :selected-dimension-ids="selectedDimensionIds"
                            :history-runs="historyRuns"
                            @select-target="selectedTargetId = $event"
                            @launch-analysis="launchAnalysis"
                            @toggle-dimension="toggleDimension"
                            @use-recommended="useRecommendedDimensions"
                            @select-run="setCurrentRun"
                        />

                        <UiLibraryPromptImproverMain
                            :is-bootstrapping="isBootstrapping"
                            :local-error="localError"
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
                            :can-launch-analysis="canLaunchAnalysis"
                            @launch-analysis="launchAnalysis"
                            @submit-clarification-answer="submitClarificationAnswer"
                            @run-improve="runImprove"
                            @update-feedback-text="feedbackText = $event"
                            @submit-feedback="submitFeedback"
                            @update-change-review="handleChangeReview"
                            @apply-to-graph="applyToGraph"
                        />
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>
