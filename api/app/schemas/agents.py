"""Agent library and execution contracts. Client profile metadata is never execution policy."""

from typing import Literal
from uuid import UUID

from models.chatDTO import EffortEnum
from models.message import ToolEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PromptLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=100000)
    enabled: bool = True


class AgentModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=255)
    reasoning_effort: EffortEnum | None = None
    exclude_reasoning: bool | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=1000000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=0)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    repetition_penalty: float | None = Field(default=None, gt=0, le=2)
    structured_output: bool = False
    retry_count: int = Field(default=0, ge=0, le=3)
    fallback_model: str | None = Field(default=None, min_length=1, max_length=255)


class AgentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handle: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,49}$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    icon: str = Field(default="LucideBot", pattern=r"^[A-Za-z][A-Za-z0-9]{0,99}$")
    accentColor: str = Field(default="#eb5e28", pattern=r"^#[0-9a-fA-F]{6}$")
    lifecycle: Literal["draft", "active", "archived"] = "draft"
    visibility: Literal["private", "public"] = "private"
    category: str = Field(default="General", max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    model_settings: AgentModelSettings
    prompt_stack: list[PromptLayer] = Field(default_factory=list, max_length=32)
    tools: list[ToolEnum] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_public(self):
        if self.visibility == "public" and self.lifecycle == "draft":
            raise ValueError("Activate an Agent before publishing it.")
        self.tags = list(dict.fromkeys(tag.strip().lower() for tag in self.tags if tag.strip()))
        self.tools = list(dict.fromkeys(self.tools))
        return self


class TeamWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    handle: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]{1,49}$")
    members: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_members(self):
        if len(set(self.members)) != len(self.members):
            raise ValueError("A Team cannot contain duplicate members.")
        return self


class AgentImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    profile: AgentWrite


class RatingWrite(BaseModel):
    value: int = Field(ge=1, le=5, strict=True)


class VerificationWrite(BaseModel):
    verified: bool


class MentionRequest(BaseModel):
    message: str = Field(max_length=100000)


class DelegationCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    instructions: str = Field(min_length=1, max_length=20000)


class DelegationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calls: list[DelegationCall] = Field(min_length=1, max_length=16)


class DelegationLimits(BaseModel):
    concurrency: int = Field(default=4, ge=1, le=8)
    total_calls: int = Field(default=16, ge=1, le=64)
    rounds: int = Field(default=6, ge=1, le=16)
    budget_seconds: int = Field(default=600, ge=1, le=1800)


class AgentNodeConfig(BaseModel):
    model: str = Field(min_length=1, max_length=255)
    teamId: UUID
    selectedTools: list[ToolEnum] = Field(default_factory=list, max_length=6)
    autoSelectTools: bool | None = False
