export interface PromptImproverDimension {
    id: string;
    label: string;
    category: string;
    description: string;
    tier: number;
}

export interface PromptImproverCategory {
    id: string;
    label: string;
    dimensions: PromptImproverDimension[];
}

export interface PromptImproverTaxonomyResponse {
    categories: PromptImproverCategory[];
}

export interface PromptImproverTarget {
    id: string;
    nodeId: string | null;
    nodeType: string;
    label: string;
    modelId: string | null;
    modelName: string | null;
    isDefaultFallback: boolean;
    toolsSupport: boolean;
}

export interface PromptImproverIssue {
    id: string;
    label: string;
    severity: string;
    description: string;
}

export type PromptImproverDimensionScoreCategory =
    | 'missing'
    | 'weak'
    | 'adequate'
    | 'strong'
    | 'excellent';

export interface PromptImproverDimensionScore {
    dimensionId: string;
    score: PromptImproverDimensionScoreCategory;
    note: string;
}

export interface PromptImproverAudit {
    healthScore: number;
    summary: string;
    detectedIssues: PromptImproverIssue[];
    dimensionScores: PromptImproverDimensionScore[];
}

export interface PromptImproverClarificationRound {
    id: string;
    status: string;
    arguments: Record<string, unknown> | unknown[];
    result: Record<string, unknown> | unknown[];
    createdAt: string | null;
}

export interface PromptImproverTemplateSnapshot {
    id: string;
    name: string;
    description: string | null;
    templateText: string;
}

export interface PromptImproverChange {
    id: string;
    orderIndex: number;
    sourceStart: number;
    sourceEnd: number;
    sourceText: string;
    suggestedText: string;
    title: string | null;
    dimensionId: string | null;
    rationale: string | null;
    impact: string | null;
    reviewStatus: string;
}

export interface PromptImproverRun {
    id: string;
    parentRunId: string | null;
    nodeId: string;
    target: PromptImproverTarget;
    optimizerModelId: string | null;
    optimizerModelName: string | null;
    optimizerToolsSupport: boolean;
    sourcePrompt: string;
    sourceTemplateSnapshot: PromptImproverTemplateSnapshot | null;
    selectedDimensionIds: string[];
    recommendedDimensionIds: string[];
    audit: PromptImproverAudit | null;
    improvedPrompt: string | null;
    composedPrompt: string;
    feedback: string | null;
    status: string;
    activePhase: string | null;
    activeToolCallId: string | null;
    clarificationRounds: PromptImproverClarificationRound[];
    changes: PromptImproverChange[];
    createdAt: string;
    updatedAt: string;
}

export interface PromptImproverDraftResponse {
    requiresTargetSelection: boolean;
    currentPrompt: string;
    targets: PromptImproverTarget[];
    activeRun: PromptImproverRun | null;
    history: PromptImproverRun[];
}

export interface PromptImproverNodeHistoryResponse {
    targets: PromptImproverTarget[];
    runs: PromptImproverRun[];
}

export interface PromptImproverReviewChangeInput {
    changeId: string;
    reviewStatus: string;
}
