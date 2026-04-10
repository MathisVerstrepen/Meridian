from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class InferenceProviderEnum(str, Enum):
    OPENROUTER = "openrouter"
    CLAUDE_AGENT = "claude_agent"


class BillingTypeEnum(str, Enum):
    METERED = "metered"
    SUBSCRIPTION = "subscription"


class Architecture(BaseModel):
    input_modalities: list[str]
    instruct_type: Optional[str] = None
    modality: str
    output_modalities: list[str]
    tokenizer: str


class Pricing(BaseModel):
    completion: str
    image: Optional[str] = None
    internal_reasoning: Optional[str] = None
    prompt: str
    request: Optional[str] = None
    web_search: Optional[str] = None


class TopProvider(BaseModel):
    context_length: Optional[int] = -1
    is_moderated: bool
    max_completion_tokens: Optional[int] = None


class ModelInfo(BaseModel):
    architecture: Architecture
    context_length: Optional[int] = -1
    created: Optional[str] = None
    id: str
    name: str
    icon: Optional[str] = None
    pricing: Pricing
    provider: InferenceProviderEnum = InferenceProviderEnum.OPENROUTER
    billingType: BillingTypeEnum = BillingTypeEnum.METERED
    requiresConnection: bool = False
    supportsStructuredOutputs: bool = True
    supportsMeridianTools: bool = False
    supportedMeridianToolNames: list[str] = []
    toolsSupport: bool = False

    @field_validator("created", mode="before")
    @classmethod
    def normalize_created(cls, value: object) -> object:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        return str(value)


class ResponseModel(BaseModel):
    data: list[ModelInfo]


class InferenceProviderStatus(BaseModel):
    provider: InferenceProviderEnum
    label: str
    isConnected: bool
    requiresUserToken: bool = True


class InferenceProviderStatusResponse(BaseModel):
    providers: list[InferenceProviderStatus]


class ClaudeAgentTokenPayload(BaseModel):
    token: str


class InferenceCredentials(BaseModel):
    openrouter_api_key: Optional[str] = None
    claude_agent_oauth_token: Optional[str] = None
