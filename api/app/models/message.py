from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

IMG_EXT_TO_MIME_TYPE = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


class MessageRoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class UsageRequest(BaseModel):
    index: int = 0
    model: str | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    request_id: str | None = None
    tool_call_count: int = 0
    tool_names: list[str] = []
    cost: float = 0.0
    is_byok: bool = True
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_tokens_details: dict[str, int] = {}
    cost_details: dict[str, float] = {}
    completion_tokens_details: dict[str, int] = {}


class UsageData(BaseModel):
    cost: float = 0.0
    is_byok: bool = True
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_tokens_details: dict[str, int] = {}
    cost_details: dict[str, float] = {}
    completion_tokens_details: dict[str, int] = {}
    requests: list[UsageRequest] = []


class MessageContentTypeEnum(str, Enum):
    text = "text"
    file = "file"
    image_url = "image_url"


class MessageContentFile(BaseModel):
    filename: str
    file_data: str  # Base64 encoded file when send to openrouter / Id when send to frontend
    id: str | None = None  # The file's UUID
    hash: str | None = None  # The file's SHA-256 content hash


class MessageContentImageURL(BaseModel):
    url: str
    id: str | None = None


class MessageContent(BaseModel):
    type: MessageContentTypeEnum
    text: str | None = None
    file: MessageContentFile | None = None
    image_url: MessageContentImageURL | None = None


class NodeTypeEnum(str, Enum):
    PROMPT = "prompt"
    TEXT_TO_TEXT = "textToText"
    PARALLELIZATION = "parallelization"
    PARALLELIZATION_MODELS = "parallelizationModels"
    FILE_PROMPT = "filePrompt"
    ROUTING = "routing"
    GITHUB = "github"
    CONTEXT_MERGER = "contextMerger"


class Message(BaseModel):
    role: MessageRoleEnum
    content: list[MessageContent]
    model: str | None = None
    node_id: str | None = None
    type: NodeTypeEnum | None = None
    data: dict | list[dict] | None = None
    usageData: UsageData | None = None
    annotations: list | None = None
    metadata: Optional[dict[str, Any]] = None


class ToolEnum(str, Enum):
    WEB_SEARCH = "web_search"
    LINK_EXTRACTION = "link_extraction"
    IMAGE_GENERATION = "image_generation"
    EXECUTE_CODE = "execute_code"
    VISUALISE = "visualise"
    ASK_USER = "ask_user"
