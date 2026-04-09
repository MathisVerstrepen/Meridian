import { useVueFlow } from '@vue-flow/core';

import type {
    PromptImproverAudit,
    PromptImproverCategory,
    PromptImproverClarificationRound,
    PromptImproverDraftResponse,
    PromptImproverReviewChangeInput,
    PromptImproverRun,
    PromptImproverTaxonomyResponse,
    PromptImproverTarget,
} from '@/types/promptImprover';
import type { DataPrompt } from '@/types/graph';

export function usePromptImprover() {
    const graphEvents = useGraphEvents();
    const settingsStore = useSettingsStore();
    const {
        answerPromptImproverQuestion,
        createPromptImproverDraft,
        feedbackPromptImproverRun,
        getPromptImproverHistory,
        getPromptImproverTaxonomy,
        reviewPromptImproverRun,
        improvePromptImproverRun,
    } = useAPI();
    const { success, error } = useToast();
    const { modelsSettings, blockPromptSettings } = storeToRefs(settingsStore);

    const isOpen = ref(false);
    const isBootstrapping = ref(false);
    const isImproving = ref(false);
    const isReviewSaving = ref(false);
    const isApplying = ref(false);
    const isFeedbackSubmitting = ref(false);
    const isQuestionSubmitting = ref(false);
    const openGraphId = ref('');
    const openNodeId = ref('');
    const taxonomy = ref<PromptImproverTaxonomyResponse | null>(null);
    const targets = ref<PromptImproverTarget[]>([]);
    const selectedTargetId = ref<string | null>(null);
    const currentPrompt = ref('');
    const currentRun = ref<PromptImproverRun | null>(null);
    const historyRuns = ref<PromptImproverRun[]>([]);
    const feedbackText = ref('');
    const localError = ref<string | null>(null);
    const selectedDimensionIds = ref<string[]>([]);
    const selectedOptimizerModelId = ref<string | null>(null);

    const workflowSteps = ['Audit', 'Improve', 'Review', 'Apply'];

    const pendingApplyResolvers = new Map<
        string,
        { resolve: () => void; reject: (error: Error) => void }
    >();
    const staleImproveRunIds = new Set<string>();

    const currentAudit = computed<PromptImproverAudit | null>(() => currentRun.value?.audit || null);
    const selectedTarget = computed(
        () => targets.value.find((target) => target.id === selectedTargetId.value) || null,
    );
    const pendingClarificationRound = computed<PromptImproverClarificationRound | null>(() => {
        if (!currentRun.value?.activeToolCallId) {
            return null;
        }

        return (
            currentRun.value.clarificationRounds.find(
                (round) => round.id === currentRun.value?.activeToolCallId,
            ) || null
        );
    });
    const answeredClarificationRounds = computed(() =>
        (currentRun.value?.clarificationRounds || []).filter(
            (round) => round.id !== currentRun.value?.activeToolCallId,
        ),
    );
    const isAwaitingClarification = computed(
        () => currentRun.value?.status === 'pending_user_input',
    );
    const reviewStats = computed(() => {
        if (!currentRun.value) {
            return { accepted: 0, rejected: 0, pending: 0, total: 0 };
        }

        const changes = currentRun.value.changes;
        return {
            accepted: changes.filter((change) => change.reviewStatus === 'accepted').length,
            rejected: changes.filter((change) => change.reviewStatus === 'rejected').length,
            pending: changes.filter(
                (change) =>
                    change.reviewStatus !== 'accepted' && change.reviewStatus !== 'rejected',
            ).length,
            total: changes.length,
        };
    });
    const workflowStep = computed(() => {
        if (!currentRun.value) return 0;
        if (currentRun.value.status === 'pending_user_input') return 0;
        if (!currentRun.value.improvedPrompt) return 1;
        if (currentRun.value.changes.length === 0) return 2;

        const allReviewed = currentRun.value.changes.every(
            (change) => change.reviewStatus === 'accepted' || change.reviewStatus === 'rejected',
        );
        return allReviewed ? 3 : 2;
    });
    const groupedCategories = computed<PromptImproverCategory[]>(
        () => taxonomy.value?.categories || [],
    );
    const dimensionLookup = computed(() => {
        const map = new Map<string, { label: string; category: string; tier: number }>();
        for (const category of taxonomy.value?.categories || []) {
            for (const dimension of category.dimensions) {
                map.set(dimension.id, {
                    label: dimension.label,
                    category: dimension.category,
                    tier: dimension.tier,
                });
            }
        }
        return map;
    });
    const canImprove = computed(() => {
        return (
            !!currentRun.value &&
            !!currentAudit.value &&
            !isAwaitingClarification.value &&
            selectedDimensionIds.value.length > 0 &&
            !isImproving.value
        );
    });
    const canApply = computed(() => {
        return (
            !!currentRun.value?.improvedPrompt &&
            !isAwaitingClarification.value &&
            !isApplying.value &&
            !isReviewSaving.value
        );
    });
    const hasHistory = computed(() => historyRuns.value.length > 0);
    const canLaunchAnalysis = computed(() => {
        return !!selectedTargetId.value && !isBootstrapping.value;
    });
    const composedPrompt = computed(() => currentRun.value?.composedPrompt || '');
    const sourcePrompt = computed(() => currentRun.value?.sourcePrompt || currentPrompt.value);

    const resolveFallbackOptimizerModelId = (targetId?: string | null) => {
        if (
            blockPromptSettings.value.overridePromptImproverModel &&
            blockPromptSettings.value.promptImproverModel
        ) {
            return blockPromptSettings.value.promptImproverModel;
        }

        const resolvedTargetId = targetId ?? selectedTargetId.value;
        const target = targets.value.find((item) => item.id === resolvedTargetId) || null;
        return target?.modelId || modelsSettings.value.defaultModel || null;
    };

    const getPromptNodeText = (graphId: string, nodeId: string) => {
        const { findNode } = useVueFlow('main-graph-' + graphId);
        const node = findNode(nodeId);
        const data = node?.data as DataPrompt | undefined;
        return data?.prompt?.trim() || '';
    };

    const mergeRunIntoHistory = (run: PromptImproverRun) => {
        historyRuns.value = [run, ...historyRuns.value.filter((item) => item.id !== run.id)];
    };

    const syncDraftResponse = (draftResponse: PromptImproverDraftResponse) => {
        currentPrompt.value = draftResponse.currentPrompt;
        targets.value = draftResponse.targets;
        historyRuns.value = draftResponse.history;
        setCurrentRun(draftResponse.activeRun);
    };

    const isBadRequestError = (err: unknown): boolean => {
        const apiError = err as { response?: { status?: number } };
        return apiError?.response?.status === 400;
    };

    const setCurrentRun = (run: PromptImproverRun | null) => {
        currentRun.value = run;
        if (!run) {
            selectedDimensionIds.value = [];
            selectedOptimizerModelId.value = resolveFallbackOptimizerModelId();
            return;
        }

        selectedTargetId.value = run.target.id;
        selectedOptimizerModelId.value =
            run.optimizerModelId || resolveFallbackOptimizerModelId(run.target.id);
        selectedDimensionIds.value =
            run.selectedDimensionIds.length > 0
                ? [...run.selectedDimensionIds]
                : [...run.recommendedDimensionIds];
    };

    const resetState = () => {
        isOpen.value = false;
        isBootstrapping.value = false;
        isImproving.value = false;
        isReviewSaving.value = false;
        isApplying.value = false;
        isFeedbackSubmitting.value = false;
        isQuestionSubmitting.value = false;
        openGraphId.value = '';
        openNodeId.value = '';
        targets.value = [];
        selectedTargetId.value = null;
        currentPrompt.value = '';
        currentRun.value = null;
        historyRuns.value = [];
        feedbackText.value = '';
        localError.value = null;
        selectedDimensionIds.value = [];
        selectedOptimizerModelId.value = null;
        staleImproveRunIds.clear();
    };

    const close = () => {
        resetState();
    };

    watch(selectedTargetId, (targetId) => {
        if (!currentRun.value) {
            selectedOptimizerModelId.value = resolveFallbackOptimizerModelId(targetId);
        }
    });

    const bootstrap = async (graphId: string, nodeId: string) => {
        isOpen.value = true;
        isBootstrapping.value = true;
        localError.value = null;
        openGraphId.value = graphId;
        openNodeId.value = nodeId;

        try {
            const [taxonomyResponse, historyResponse] = await Promise.all([
                taxonomy.value ? Promise.resolve(taxonomy.value) : getPromptImproverTaxonomy(),
                getPromptImproverHistory(graphId, nodeId),
            ]);

            if (!taxonomy.value) {
                taxonomy.value = taxonomyResponse;
            }

            historyRuns.value = historyResponse.runs;
            targets.value = historyResponse.targets;
            selectedTargetId.value =
                historyResponse.runs[0]?.target.id ||
                (historyResponse.targets.length === 1 ? historyResponse.targets[0].id : null);
            setCurrentRun(historyResponse.runs[0] || null);
        } catch (err) {
            console.error('Failed to open prompt improver:', err);
            localError.value = 'Failed to load prompt improver data.';
        } finally {
            isBootstrapping.value = false;
        }
    };

    const launchAnalysis = async () => {
        if (!openGraphId.value || !openNodeId.value || !selectedTargetId.value) return;
        isBootstrapping.value = true;
        localError.value = null;

        try {
            const draftResponse = await createPromptImproverDraft(
                openGraphId.value,
                openNodeId.value,
                selectedTargetId.value,
                selectedOptimizerModelId.value,
            );
            syncDraftResponse(draftResponse);
        } catch (err) {
            console.error('Failed to analyze prompt for target:', err);
            localError.value = 'Failed to analyze the prompt for the selected target.';
        } finally {
            isBootstrapping.value = false;
        }
    };

    const createFreshImproveRun = async () => {
        if (!openGraphId.value || !openNodeId.value || !selectedTargetId.value) {
            throw new Error('Prompt improver is missing graph context for retry.');
        }

        const preservedDimensionIds = [...selectedDimensionIds.value];
        const preservedOptimizerModelId = selectedOptimizerModelId.value;
        const draftResponse = await createPromptImproverDraft(
            openGraphId.value,
            openNodeId.value,
            selectedTargetId.value,
            preservedOptimizerModelId,
        );
        syncDraftResponse(draftResponse);
        selectedDimensionIds.value = preservedDimensionIds;
        selectedOptimizerModelId.value = preservedOptimizerModelId;

        if (!draftResponse.activeRun) {
            throw new Error('Prompt improver retry did not return an active run.');
        }

        return draftResponse.activeRun;
    };

    const toggleDimension = (dimensionId: string) => {
        if (selectedDimensionIds.value.includes(dimensionId)) {
            selectedDimensionIds.value = selectedDimensionIds.value.filter((id) => id !== dimensionId);
            return;
        }

        selectedDimensionIds.value = [...selectedDimensionIds.value, dimensionId];
    };

    const useRecommendedDimensions = () => {
        if (!currentRun.value) {
            return;
        }

        selectedDimensionIds.value = [...currentRun.value.recommendedDimensionIds];
    };

    const runImprove = async () => {
        if (!currentRun.value) return;
        isImproving.value = true;
        localError.value = null;

        try {
            const runToImprove =
                currentRun.value.status === 'failed' || staleImproveRunIds.has(currentRun.value.id)
                    ? await createFreshImproveRun()
                    : currentRun.value;
            const nextRun = await improvePromptImproverRun(
                runToImprove.id,
                selectedDimensionIds.value,
                selectedOptimizerModelId.value,
            );
            staleImproveRunIds.delete(nextRun.id);
            setCurrentRun(nextRun);
            mergeRunIntoHistory(nextRun);
        } catch (err) {
            console.error('Failed to improve prompt:', err);
            if (currentRun.value && isBadRequestError(err)) {
                staleImproveRunIds.add(currentRun.value.id);
                localError.value =
                    'Prompt improvement failed. Retry will start a fresh run.';
            } else {
                localError.value = 'Prompt improvement failed.';
            }
        } finally {
            isImproving.value = false;
        }
    };

    const persistReview = async (
        changes: PromptImproverReviewChangeInput[],
        markApplied: boolean = false,
    ) => {
        if (!currentRun.value) return;
        isReviewSaving.value = !markApplied;
        try {
            const nextRun = await reviewPromptImproverRun(currentRun.value.id, changes, markApplied);
            setCurrentRun(nextRun);
            mergeRunIntoHistory(nextRun);
            return nextRun;
        } finally {
            if (!markApplied) {
                isReviewSaving.value = false;
            }
        }
    };

    const updateChangeReview = async (changeId: string, reviewStatus: string) => {
        if (!currentRun.value) return;
        const changes = currentRun.value.changes.map((change) => ({
            changeId: change.id,
            reviewStatus: change.id === changeId ? reviewStatus : change.reviewStatus,
        }));

        try {
            await persistReview(changes);
        } catch (err) {
            console.error('Failed to save prompt review:', err);
            error('Failed to save your review changes.');
        }
    };

    const submitFeedback = async () => {
        if (!currentRun.value || !feedbackText.value.trim() || isAwaitingClarification.value) return;
        isFeedbackSubmitting.value = true;
        localError.value = null;

        try {
            const nextRun = await feedbackPromptImproverRun(
                currentRun.value.id,
                feedbackText.value.trim(),
                selectedDimensionIds.value,
                selectedOptimizerModelId.value,
            );
            feedbackText.value = '';
            setCurrentRun(nextRun);
            mergeRunIntoHistory(nextRun);
        } catch (err) {
            console.error('Failed to submit prompt feedback:', err);
            localError.value = 'Feedback re-improvement failed.';
        } finally {
            isFeedbackSubmitting.value = false;
        }
    };

    const submitClarificationAnswer = async (answer: Record<string, unknown>) => {
        if (!currentRun.value || !pendingClarificationRound.value) return;
        isQuestionSubmitting.value = true;
        localError.value = null;

        try {
            const nextRun = await answerPromptImproverQuestion(
                currentRun.value.id,
                pendingClarificationRound.value.id,
                answer,
                selectedOptimizerModelId.value,
            );
            setCurrentRun(nextRun);
            mergeRunIntoHistory(nextRun);
        } catch (err) {
            console.error('Failed to answer prompt improver question:', err);
            localError.value = 'Failed to submit clarification answers.';
        } finally {
            isQuestionSubmitting.value = false;
        }
    };

    const applyToGraph = async () => {
        if (!currentRun.value) return;
        isApplying.value = true;
        const reviewChanges = currentRun.value.changes.map((change) => ({
            changeId: change.id,
            reviewStatus: change.reviewStatus,
        }));

        try {
            graphEvents.emit('apply-prompt-improver', {
                graphId: openGraphId.value,
                nodeId: openNodeId.value,
                promptText: currentRun.value.composedPrompt,
                detachTemplate: !!currentRun.value.sourceTemplateSnapshot,
                runId: currentRun.value.id,
                changes: reviewChanges,
            });

            await new Promise<void>((resolve, reject) => {
                pendingApplyResolvers.set(openNodeId.value, { resolve, reject });
            });

            const nextRun = await persistReview(reviewChanges, true);
            if (nextRun) {
                mergeRunIntoHistory(nextRun);
            }
            success('Prompt applied to node.');
            close();
        } catch (err) {
            console.error('Failed to apply improved prompt:', err);
            error((err as Error).message || 'Failed to apply improved prompt.');
        } finally {
            isApplying.value = false;
        }
    };

    let removeOpenListener: (() => void) | null = null;
    let removeApplyListener: (() => void) | null = null;
    let handleKeyDown: ((event: KeyboardEvent) => void) | null = null;

    onMounted(() => {
        removeOpenListener = graphEvents.on('open-prompt-improver', ({ graphId, nodeId }) => {
            if (!getPromptNodeText(graphId, nodeId)) {
                error('Set a prompt before opening the prompt improver.');
                return;
            }

            bootstrap(graphId, nodeId);
        });

        removeApplyListener = graphEvents.on(
            'prompt-improver-applied',
            ({ nodeId, success, error }) => {
                const resolver = pendingApplyResolvers.get(nodeId);
                if (!resolver) return;

                pendingApplyResolvers.delete(nodeId);
                if (success) {
                    resolver.resolve();
                    return;
                }

                resolver.reject(
                    new Error(error || 'Failed to save the graph after applying changes.'),
                );
            },
        );

        handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && isOpen.value) {
                close();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
    });

    onUnmounted(() => {
        removeOpenListener?.();
        removeApplyListener?.();
        if (handleKeyDown) {
            window.removeEventListener('keydown', handleKeyDown);
        }
    });

    return {
        isOpen,
        isBootstrapping,
        isImproving,
        isReviewSaving,
        isApplying,
        isFeedbackSubmitting,
        isQuestionSubmitting,
        targets,
        selectedTargetId,
        currentRun,
        selectedOptimizerModelId,
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
    };
}
