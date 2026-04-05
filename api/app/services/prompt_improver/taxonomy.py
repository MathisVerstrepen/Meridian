import json

from models.prompt_improver import (
    PromptImproverAudit,
    PromptImproverCategory,
    PromptImproverDimension,
    PromptImproverDimensionScore,
    PromptImproverIssue,
    PromptImproverTaxonomyResponse,
)

from .schemas import (
    DIMENSION_SCORE_RANK,
    AnalyzerResponseSchema,
    DimensionMeta,
    IssueDetectorResponseSchema,
    default_dimension_scores,
)

TAXONOMY_DEFINITIONS: list[DimensionMeta] = [
    DimensionMeta(
        "clarity_specificity", "Clarity", "content", "Remove ambiguity and make asks precise.", 1
    ),
    DimensionMeta(
        "context_provision",
        "Context",
        "content",
        "Ground the model with task context and references.",
        1,
    ),
    DimensionMeta(
        "task_specification",
        "Task Spec",
        "content",
        "State the exact job, scope, and expected outcome.",
        2,
    ),
    DimensionMeta(
        "audience_definition",
        "Audience",
        "content",
        "Clarify who the output is for and what they need.",
        3,
    ),
    DimensionMeta(
        "structural_formatting",
        "Formatting",
        "structure",
        "Use sections, tags, or headings for readable structure.",
        1,
    ),
    DimensionMeta(
        "instruction_ordering",
        "Instruction Order",
        "structure",
        "Put the highest-priority instructions first.",
        2,
    ),
    DimensionMeta(
        "delimiters",
        "Delimiters",
        "structure",
        "Separate instructions, context, and examples clearly.",
        2,
    ),
    DimensionMeta(
        "length_optimization", "Length", "structure", "Trim prompt bloat without losing intent.", 4
    ),
    DimensionMeta(
        "chain_of_thought",
        "Reasoning Steps",
        "reasoning",
        "Ask for explicit reasoning only when the task benefits.",
        1,
    ),
    DimensionMeta(
        "task_decomposition",
        "Decomposition",
        "reasoning",
        "Break complex work into smaller ordered steps.",
        2,
    ),
    DimensionMeta(
        "self_reflection",
        "Self Review",
        "reasoning",
        "Ask the model to check its work before finalizing.",
        3,
    ),
    DimensionMeta(
        "role_persona", "Role", "behavior", "Assign an explicit role or expertise lens.", 2
    ),
    DimensionMeta(
        "tone_style", "Tone", "behavior", "Specify the tone and style when it matters.", 3
    ),
    DimensionMeta(
        "behavioral_constraints",
        "Constraints",
        "behavior",
        "Add rules on what to do and what to avoid.",
        3,
    ),
    DimensionMeta(
        "few_shot_examples",
        "Few-Shot Examples",
        "examples",
        "Provide strong demonstrations of desired behavior.",
        1,
    ),
    DimensionMeta(
        "negative_examples",
        "Negative Examples",
        "examples",
        "Show failure cases or what to avoid.",
        3,
    ),
    DimensionMeta(
        "example_diversity",
        "Example Diversity",
        "examples",
        "Use examples that span typical and edge cases.",
        3,
    ),
    DimensionMeta(
        "output_format", "Output Format", "output", "Specify the response format explicitly.", 2
    ),
    DimensionMeta(
        "length_control",
        "Length Control",
        "output",
        "Set length or verbosity bounds for the result.",
        3,
    ),
    DimensionMeta(
        "evaluation_criteria",
        "Evaluation Criteria",
        "output",
        "State how the output should be judged.",
        3,
    ),
    DimensionMeta(
        "safety_guardrails", "Guardrails", "safety", "Add safety, refusal, or escalation rules.", 2
    ),
    DimensionMeta(
        "injection_defense",
        "Injection Defense",
        "safety",
        "Harden the prompt against malicious instructions.",
        3,
    ),
    DimensionMeta(
        "hallucination_reduction",
        "Hallucination Reduction",
        "safety",
        "Require uncertainty handling and evidence use.",
        3,
    ),
    DimensionMeta(
        "error_handling",
        "Error Handling",
        "safety",
        "Specify what the model should do when information is missing.",
        3,
    ),
    DimensionMeta(
        "variables_templates",
        "Variables",
        "engineering",
        "Preserve placeholders and reusable prompt variables.",
        4,
    ),
]

CATEGORY_LABELS = {
    "content": "Content",
    "structure": "Structure",
    "reasoning": "Reasoning",
    "behavior": "Behavior",
    "examples": "Examples",
    "output": "Output",
    "safety": "Safety",
    "engineering": "Engineering",
}

DEFAULT_TARGET_ID = "__default__"


def get_prompt_improver_taxonomy() -> PromptImproverTaxonomyResponse:
    categories: list[PromptImproverCategory] = []
    for category_id, label in CATEGORY_LABELS.items():
        categories.append(
            PromptImproverCategory(
                id=category_id,
                label=label,
                dimensions=[
                    PromptImproverDimension(
                        id=dimension.id,
                        label=dimension.label,
                        category=dimension.category,
                        description=dimension.description,
                        tier=dimension.tier,
                    )
                    for dimension in TAXONOMY_DEFINITIONS
                    if dimension.category == category_id
                ],
            )
        )
    return PromptImproverTaxonomyResponse(categories=categories)


def taxonomy_index() -> dict[str, DimensionMeta]:
    return {dimension.id: dimension for dimension in TAXONOMY_DEFINITIONS}


def sanitize_dimension_ids(dimension_ids: list[str] | None) -> list[str]:
    known = taxonomy_index()
    cleaned: list[str] = []
    for dimension_id in dimension_ids or []:
        if dimension_id in known and dimension_id not in cleaned:
            cleaned.append(dimension_id)
    return cleaned


def coerce_impact(dimension_id: str | None, fallback: str = "Medium") -> str:
    if not dimension_id:
        return fallback
    dimension = taxonomy_index().get(dimension_id)
    if not dimension:
        return fallback
    if dimension.tier == 1:
        return "High"
    if dimension.tier == 2:
        return "Medium"
    return "Low"


def normalize_audit(
    analyzer: AnalyzerResponseSchema,
    issue_detector: IssueDetectorResponseSchema,
) -> tuple[PromptImproverAudit, list[str]]:
    by_dimension = {
        score.dimension_id: PromptImproverDimensionScore(
            dimension_id=score.dimension_id,
            score=score.score,
            note=score.note,
        )
        for score in analyzer.dimension_scores
    }
    dimension_scores: list[PromptImproverDimensionScore] = []
    for default_score in default_dimension_scores(TAXONOMY_DEFINITIONS):
        dimension_scores.append(by_dimension.get(default_score.dimension_id, default_score))

    issues = [
        PromptImproverIssue.model_validate(issue.model_dump()) for issue in analyzer.detected_issues
    ]
    issue_groups = [
        ("contradiction", "Contradiction", "high", issue_detector.contradictions),
        ("ambiguity", "Ambiguity", "medium", issue_detector.ambiguities),
        ("structure", "Structure", "medium", issue_detector.structure_issues),
        ("safety", "Safety", "high", issue_detector.safety_issues),
    ]
    for issue_id, label, severity, values in issue_groups:
        for value in values:
            issues.append(
                PromptImproverIssue(
                    id=issue_id,
                    label=label,
                    severity=severity,
                    description=value,
                )
            )

    recommended_dimension_ids = sanitize_dimension_ids(analyzer.recommended_dimension_ids)
    if not recommended_dimension_ids:
        sorted_scores = sorted(
            dimension_scores,
            key=lambda item: (
                DIMENSION_SCORE_RANK.get(item.score, DIMENSION_SCORE_RANK["adequate"]),
                taxonomy_index()[item.dimension_id].tier,
            ),
        )
        recommended_dimension_ids = [score.dimension_id for score in sorted_scores[:5]]

    audit = PromptImproverAudit(
        health_score=analyzer.health_score,
        summary=analyzer.summary,
        detected_issues=issues[:10],
        dimension_scores=dimension_scores,
    )
    return audit, recommended_dimension_ids[:8]


def taxonomy_json() -> str:
    return json.dumps(get_prompt_improver_taxonomy().model_dump(mode="json"), indent=2)
