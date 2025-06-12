from pydantic import BaseModel
from enum import Enum

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


class UsageData(BaseModel):
    cost: float
    is_byok: bool
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    prompt_tokens_details: dict[str, int]
    completion_tokens_details: dict[str, int]


class MessageContentTypeEnum(str, Enum):
    text = "text"
    file = "file"
    image_url = "image_url"


class MessageContentFile(BaseModel):
    filename: str
    file_data: (
        str  # Base64 encoded file when send to openrouter / Id when send to frontend
    )


class MessageContentImageURL(BaseModel):
    url: str


class MessageContent(BaseModel):
    type: MessageContentTypeEnum
    text: str | None = None
    file: MessageContentFile | None = None
    image_url: MessageContentImageURL | None = None


class MessageTypeEnum(str, Enum):
    PROMPT = "prompt"
    TEXT_TO_TEXT = "textToText"
    PARALLELIZATION = "parallelization"
    FILE_PROMPT = "filePrompt"


class Message(BaseModel):
    role: MessageRoleEnum
    content: list[MessageContent]
    model: str | None = None
    node_id: str | None = None
    type: MessageTypeEnum | None = None
    data: dict | list[dict] = None
    usageData: UsageData | None = None
