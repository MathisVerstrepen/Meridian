from dataclasses import dataclass
from typing import Any, Literal

from models.prompt_improver import PromptImproverDimensionScore
from pydantic import BaseModel, Field

DimensionScoreCategory = Literal["missing", "weak", "adequate", "strong", "excellent"]
DIMENSION_SCORE_RANK: dict[str, int] = {
    "missing": 0,
    "weak": 1,
    "adequate": 2,
    "strong": 3,
    "excellent": 4,
}


class AnalyzerIssueSchema(BaseModel):
    id: str
    label: str
    severity: str
    description: str


class AnalyzerDimensionScoreSchema(BaseModel):
    dimension_id: str
    score: DimensionScoreCategory
    note: str


class AnalyzerResponseSchema(BaseModel):
    health_score: int = Field(ge=0, le=100)
    summary: str
    detected_issues: list[AnalyzerIssueSchema]
    recommended_dimension_ids: list[str]
    dimension_scores: list[AnalyzerDimensionScoreSchema]


class IssueDetectorResponseSchema(BaseModel):
    contradictions: list[str] = []
    ambiguities: list[str] = []
    structure_issues: list[str] = []
    safety_issues: list[str] = []
    priority_notes: list[str] = []


class ImprovementResponseSchema(BaseModel):
    improved_prompt: str


class ChangeExplanationSchema(BaseModel):
    title: str
    dimension_id: str
    rationale: str
    impact: str


class ChangeExplanationResponseSchema(BaseModel):
    explanations: list[ChangeExplanationSchema]


@dataclass(frozen=True)
class DimensionMeta:
    id: str
    label: str
    category: str
    description: str
    tier: int


@dataclass(frozen=True)
class PromptImproverContextBundle:
    sibling_context_text: str
    attachment_contents: list[dict[str, Any]]


@dataclass(frozen=True)
class PromptImproverClarificationDecision:
    pending_tool_call_id: str | None


def default_dimension_scores(
    definitions: list[DimensionMeta],
) -> list[PromptImproverDimensionScore]:
    return [
        PromptImproverDimensionScore(
            dimension_id=dimension.id,
            score="adequate",
            note="No explicit signal detected yet.",
        )
        for dimension in definitions
    ]
