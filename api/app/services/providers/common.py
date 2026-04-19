import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from database.pg.token_ops.provider_token_crud import store_provider_token_if_current_matches
from models.message import MessageContentTypeEnum, NodeTypeEnum, ToolEnum
from pydantic import BaseModel
from services.crypto import encrypt_api_key
from services.sandbox_inputs import SandboxInputFileReference
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

GENERIC_STREAM_ERROR_MESSAGE = "An unexpected server error occurred. Please try again later."
DEFAULT_EXTERNAL_TOOL_REFERENCE_NAMES = (
    "functions.update_plan",
    "functions.request_user_input",
    "functions.view_image",
    "functions.apply_patch",
    "multi_tool_use.parallel",
)
DEFAULT_EXTERNAL_TOOL_REFERENCE_PATTERN = re.compile(
    r"(?im)^.*(?:functions\.[a-z0-9_]+|multi_tool_use\.[a-z0-9_]+).*$"
)
DEFAULT_EXTERNAL_TOOL_REFERENCE_DISCLAIMER = (
    "Ignore any references to external coding-assistant tools such as functions.* or "
    "multi_tool_use.*. For this Meridian request, only use the tools explicitly exposed by "
    "the host runtime."
)
MERIDIAN_SUPPORTED_TOOL_NAMES = (
    ToolEnum.WEB_SEARCH.value,
    ToolEnum.LINK_EXTRACTION.value,
    ToolEnum.EXECUTE_CODE.value,
    ToolEnum.IMAGE_GENERATION.value,
    ToolEnum.VISUALISE.value,
    ToolEnum.ASK_USER.value,
)
MERIDIAN_SUPPORTED_TOOLS = frozenset(
    ToolEnum(tool_name) for tool_name in MERIDIAN_SUPPORTED_TOOL_NAMES
)
MERIDIAN_HTTP_CLIENT_REQUIRED_TOOLS = frozenset(
    {
        ToolEnum.WEB_SEARCH,
        ToolEnum.EXECUTE_CODE,
        ToolEnum.IMAGE_GENERATION,
        ToolEnum.VISUALISE,
    }
)
MERIDIAN_HTTP_CLIENT_REQUIRED_TOOLS_WITH_LINK_EXTRACTION = frozenset(
    {*MERIDIAN_HTTP_CLIENT_REQUIRED_TOOLS, ToolEnum.LINK_EXTRACTION}
)
STREAM_QUEUE_POLL_INTERVAL_SECONDS = 0.1
_T = TypeVar("_T")


@dataclass
class ThinkingState:
    is_open: bool = False

    def open_chunk(self) -> str:
        if self.is_open:
            return ""
        self.is_open = True
        return "[THINK]\n"

    def close_chunk(self) -> str:
        if not self.is_open:
            return ""
        self.is_open = False
        return "\n[!THINK]\n"

    def wrap_text(self, text: str) -> str:
        if not text:
            return ""
        return f"[THINK]\n{text}\n[!THINK]\n"


@dataclass(kw_only=True)
class BaseProviderReq:
    model: str
    messages: list[Any] | list[dict[str, Any]]
    config: Any
    user_id: str
    pg_engine: SQLAlchemyAsyncEngine
    model_id: str | None = None
    node_id: str | None = None
    graph_id: str | None = None
    is_title_generation: bool = False
    node_type: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT
    schema: type[BaseModel] | None = None
    stream: bool = True
    http_client: Any = None
    file_uuids: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)
    pdf_engine: str = "default"
    selected_tools: list[ToolEnum] = field(default_factory=list)
    sandbox_input_files: list[SandboxInputFileReference] = field(default_factory=list)
    sandbox_input_warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.messages = [
            message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else message
            for message in self.messages
        ]
        self.file_uuids = list(self.file_uuids or [])
        self.file_hashes = dict(self.file_hashes or {})
        self.selected_tools = normalize_selected_tools(self.selected_tools)
        self.sandbox_input_files = list(self.sandbox_input_files or [])
        self.sandbox_input_warnings = list(self.sandbox_input_warnings or [])


def validate_supported_tools(
    provider_label: str,
    selected_tools: list[ToolEnum],
    *,
    supported_tools: frozenset[ToolEnum] = MERIDIAN_SUPPORTED_TOOLS,
) -> None:
    unsupported_tools = [tool.value for tool in selected_tools if tool not in supported_tools]
    if unsupported_tools:
        raise ValueError(
            f"{provider_label} models currently support only these Meridian tools: "
            + ", ".join(MERIDIAN_SUPPORTED_TOOL_NAMES)
            + ". Unsupported selection: "
            + ", ".join(unsupported_tools)
            + "."
        )


def validate_http_client_for_tools(
    provider_label: str,
    selected_tools: list[ToolEnum],
    http_client: Any,
    *,
    required_tools: frozenset[ToolEnum] = MERIDIAN_HTTP_CLIENT_REQUIRED_TOOLS,
) -> None:
    if http_client is None and any(tool in required_tools for tool in selected_tools):
        raise ValueError(
            f"{provider_label} tool execution requires an HTTP client in this request."
        )


async def stream_background_task_chunks(
    queue: asyncio.Queue[_T],
    *,
    task: asyncio.Task[Any] | None = None,
    completion_event: asyncio.Event | None = None,
    poll_interval: float = STREAM_QUEUE_POLL_INTERVAL_SECONDS,
) -> AsyncIterator[_T]:
    while True:
        if completion_event is not None:
            should_stop = completion_event.is_set() and queue.empty()
        else:
            should_stop = task is not None and task.done() and queue.empty()
        if should_stop:
            break

        try:
            yield await asyncio.wait_for(queue.get(), timeout=poll_interval)
        except asyncio.TimeoutError:
            continue


def sanitize_external_tool_references(
    raw_instructions: str,
    *,
    forbidden_tool_names: tuple[str, ...] = DEFAULT_EXTERNAL_TOOL_REFERENCE_NAMES,
    tool_reference_pattern: re.Pattern[str] = DEFAULT_EXTERNAL_TOOL_REFERENCE_PATTERN,
    disclaimer: str = DEFAULT_EXTERNAL_TOOL_REFERENCE_DISCLAIMER,
) -> str:
    if not raw_instructions.strip():
        return ""

    filtered_lines: list[str] = []
    removed_external_tool_reference = False

    for raw_line in raw_instructions.splitlines():
        stripped_line = raw_line.strip()
        if stripped_line and any(tool_name in stripped_line for tool_name in forbidden_tool_names):
            removed_external_tool_reference = True
            continue

        if tool_reference_pattern.match(raw_line):
            removed_external_tool_reference = True
            continue

        filtered_lines.append(raw_line.rstrip())

    sanitized = "\n".join(filtered_lines).strip()
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    if removed_external_tool_reference:
        if sanitized:
            sanitized = f"{sanitized}\n\n{disclaimer}"
        else:
            sanitized = disclaimer

    return sanitized.strip()


async def persist_refreshed_provider_token(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider_key: str,
    current_value: str,
    refreshed_value: str | None,
    normalize_fn: Callable[[str], str],
    value_label: str,
    merge_fn: Callable[[str, str], str] | None = None,
    on_success: Callable[[str], None] | None = None,
    raise_on_encrypt_failure: bool = True,
) -> str | None:
    if not refreshed_value:
        return None

    normalized_current = normalize_fn(current_value)
    normalized_refreshed = (
        merge_fn(current_value, refreshed_value)
        if merge_fn is not None
        else normalize_fn(refreshed_value)
    )
    if normalized_current == normalized_refreshed:
        return normalized_refreshed

    encrypted_value = await encrypt_api_key(normalized_refreshed)
    if not encrypted_value:
        message = f"Failed to encrypt refreshed {value_label}."
        if raise_on_encrypt_failure:
            raise ValueError(message)
        logger.warning(message)
        return None

    stored = await store_provider_token_if_current_matches(
        pg_engine,
        user_id,
        provider_key,
        normalized_current,
        encrypted_value,
    )
    if not stored:
        logger.info(
            "Skipped storing refreshed %s for user %s due to concurrent update.",
            value_label,
            user_id,
        )
        return None

    if on_success is not None:
        on_success(normalized_refreshed)
    return normalized_refreshed


def strip_model_prefix(model_id: str, prefix: str) -> str:
    if model_id.startswith(prefix):
        return model_id[len(prefix) :]
    return model_id


def normalize_role_value(role: Any) -> str:
    if isinstance(role, Enum):
        normalized = str(role.value or "").strip()
    elif isinstance(role, str):
        normalized = role.strip()
    else:
        normalized = str(role or "").strip()

    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]

    return normalized.lower() or "user"


def extract_text_content(content: Any, *, strip: bool = True) -> str:
    if isinstance(content, str):
        return content.strip() if strip else content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != MessageContentTypeEnum.text.value or not item.get("text"):
            continue
        text = str(item["text"])
        parts.append(text.strip() if strip else text)
    return "\n".join(part for part in parts if part)


def has_message_part_type(messages: Iterable[dict[str, Any]], part_type: str) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == part_type:
                return True
    return False


def has_file_attachments(messages: Iterable[dict[str, Any]]) -> bool:
    return has_message_part_type(messages, MessageContentTypeEnum.file.value)


def has_image_inputs(messages: Iterable[dict[str, Any]]) -> bool:
    return has_message_part_type(messages, MessageContentTypeEnum.image_url.value)


def normalize_temperature(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(parsed, 1.0))


def normalize_top_p(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return 0.01
    return max(0.01, min(parsed, 1.0))


def normalize_max_tokens(
    value: Any,
    *,
    fallback: int | None = None,
    maximum: int = 131072,
) -> int | None:
    if value is None:
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    if parsed <= 0:
        return fallback
    return min(parsed, maximum)


def extract_reasoning_text_delta(
    delta: dict[str, Any],
    *,
    thinking_started: bool,
) -> tuple[str, bool]:
    content_to_yield = ""

    reasoning_content = delta.get("reasoning_content") or delta.get("reasoning")
    if reasoning_content:
        if not thinking_started:
            content_to_yield += "[THINK]\n"
            thinking_started = True
        content_to_yield += str(reasoning_content)

    content = delta.get("content")
    if content:
        if thinking_started:
            content_to_yield += "\n[!THINK]\n"
            thinking_started = False
        content_to_yield += str(content)

    return content_to_yield, thinking_started


def write_private_file(path: Path, content: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def split_system_prompt(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    non_system_messages: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "")
        if role == "system":
            system_parts.append(extract_text_content(message.get("content")))
            continue
        non_system_messages.append(message)
    return "\n\n".join(part for part in system_parts if part), non_system_messages


def build_prompt(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user")
        name = str(message.get("name") or "").strip()
        content_text = extract_text_content(message.get("content"))
        if not content_text and role == "tool":
            try:
                content_text = json.dumps(json.loads(str(message.get("content") or "")), indent=2)
            except (TypeError, json.JSONDecodeError):
                content_text = str(message.get("content") or "")
        if not content_text:
            continue

        heading = f"Tool ({name})" if role == "tool" and name else role.capitalize()
        lines.append(f"{heading}:\n{content_text}")
    return "\n\n".join(lines).strip()


def normalize_selected_tools(selected_tools: list[Any] | None) -> list[ToolEnum]:
    normalized: list[ToolEnum] = []
    for tool_value in selected_tools or []:
        try:
            parsed = (
                tool_value
                if isinstance(tool_value, ToolEnum)
                else ToolEnum(str(getattr(tool_value, "value", tool_value)))
            )
        except ValueError:
            continue
        if parsed not in normalized:
            normalized.append(parsed)
    return normalized


def normalize_tool_storage_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): normalize_tool_storage_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_tool_storage_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def serialize_sandbox_input_files(
    input_files: Iterable[SandboxInputFileReference | Any],
) -> list[dict[str, Any]]:
    return [
        {
            "file_id": input_file.file_id,
            "storage_path": input_file.storage_path,
            "relative_path": input_file.relative_path,
            "name": input_file.name,
            "content_type": input_file.content_type,
            "size": input_file.size,
        }
        for input_file in input_files
    ]
