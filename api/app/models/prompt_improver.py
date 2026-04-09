from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel


class PromptImproverDimension(BaseModel):
    id: str
    label: str
    category: str
    description: str
    tier: int = Field(ge=1, le=4)

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverCategory(BaseModel):
    id: str
    label: str
    dimensions: list[PromptImproverDimension]

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverTaxonomyResponse(BaseModel):
    categories: list[PromptImproverCategory]

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverTarget(BaseModel):
    id: str
    node_id: Optional[str] = None
    node_type: str
    label: str
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    is_default_fallback: bool = False
    tools_support: bool = False

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverIssue(BaseModel):
    id: str
    label: str
    severity: str
    description: str

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverDimensionScore(BaseModel):
    dimension_id: str
    score: Literal["missing", "weak", "adequate", "strong", "excellent"]
    note: str

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverAudit(BaseModel):
    health_score: int = Field(ge=0, le=100)
    summary: str
    detected_issues: list[PromptImproverIssue]
    dimension_scores: list[PromptImproverDimensionScore]

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverClarificationRound(BaseModel):
    id: str
    status: str
    arguments: dict | list
    result: dict | list
    created_at: Optional[datetime] = None

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverTemplateSnapshot(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    template_text: str

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverChangeRead(BaseModel):
    id: str
    order_index: int
    source_start: int
    source_end: int
    source_text: str
    suggested_text: str
    title: Optional[str] = None
    dimension_id: Optional[str] = None
    rationale: Optional[str] = None
    impact: Optional[str] = None
    review_status: str

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverRunRead(BaseModel):
    id: str
    parent_run_id: Optional[str] = None
    node_id: str
    target: PromptImproverTarget
    optimizer_model_id: Optional[str] = None
    optimizer_model_name: Optional[str] = None
    optimizer_tools_support: bool = False
    source_prompt: str
    source_template_snapshot: Optional[PromptImproverTemplateSnapshot] = None
    selected_dimension_ids: list[str]
    recommended_dimension_ids: list[str]
    audit: Optional[PromptImproverAudit] = None
    improved_prompt: Optional[str] = None
    composed_prompt: str
    feedback: Optional[str] = None
    status: str
    active_phase: Optional[str] = None
    active_tool_call_id: Optional[str] = None
    clarification_rounds: list[PromptImproverClarificationRound] = Field(default_factory=list)
    changes: list[PromptImproverChangeRead]
    created_at: datetime
    updated_at: datetime

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverNodeHistoryResponse(BaseModel):
    targets: list[PromptImproverTarget]
    runs: list[PromptImproverRunRead]

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverDraftRequest(BaseModel):
    graph_id: str
    node_id: str
    target_id: Optional[str] = None
    optimizer_model_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverDraftResponse(BaseModel):
    requires_target_selection: bool
    current_prompt: str
    targets: list[PromptImproverTarget]
    active_run: Optional[PromptImproverRunRead] = None
    history: list[PromptImproverRunRead]

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverImproveRequest(BaseModel):
    selected_dimension_ids: list[str] = Field(default_factory=list)
    optimizer_model_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverReviewChangeInput(BaseModel):
    change_id: str
    review_status: str

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverReviewRequest(BaseModel):
    changes: list[PromptImproverReviewChangeInput] = Field(default_factory=list)
    mark_applied: bool = False

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverFeedbackRequest(BaseModel):
    feedback: str = Field(min_length=1)
    selected_dimension_ids: list[str] = Field(default_factory=list)
    optimizer_model_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        validate_by_name = True


class PromptImproverQuestionAnswerRequest(BaseModel):
    tool_call_id: str
    answer: object
    optimizer_model_id: Optional[str] = None

    class Config:
        alias_generator = to_camel
        validate_by_name = True
