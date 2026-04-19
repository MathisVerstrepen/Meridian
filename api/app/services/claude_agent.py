import json
import logging
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, Optional, cast

import sentry_sdk
from database.pg.chat_ops import create_tool_call
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.models import ToolCallStatusEnum
from database.redis.redis_ops import RedisManager
from models.message import MessageContentTypeEnum, NodeTypeEnum, ToolEnum
from models.tool_question import AskUserPendingResult
from services.graph_service import Message
from services.provider_runtime import (
    is_runtime_dir_stale,
    start_runtime_heartbeat,
    stop_runtime_heartbeat,
    touch_runtime_heartbeat,
)
from services.providers.claude_agent_catalog import CLAUDE_AGENT_MODEL_PREFIX
from services.tools import get_tool_runtime, resolve_tool_status
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")
CLAUDE_AGENT_RUNTIME_PREFIX = "meridian-claude-agent-"
CLAUDE_AGENT_RUNTIME_ROOT = Path("/tmp")
CLAUDE_AGENT_RUNTIME_TTL_SECONDS = 60 * 60

try:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool
    from claude_agent_sdk.types import (
        AssistantMessage,
        PermissionResultAllow,
        ResultMessage,
        StreamEvent,
        TextBlock,
        ThinkingBlock,
    )

    CLAUDE_AGENT_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without the SDK
    ClaudeAgentOptions = None  # type: ignore[misc,assignment]
    ClaudeSDKClient = None  # type: ignore[misc,assignment]
    create_sdk_mcp_server = None  # type: ignore[misc,assignment]
    tool = None  # type: ignore[misc,assignment]
    AssistantMessage = None  # type: ignore[misc,assignment]
    PermissionResultAllow = None  # type: ignore[misc,assignment]
    ResultMessage = None  # type: ignore[misc,assignment]
    StreamEvent = None  # type: ignore[misc,assignment]
    TextBlock = None  # type: ignore[misc,assignment]
    ThinkingBlock = None  # type: ignore[misc,assignment]
    CLAUDE_AGENT_SDK_AVAILABLE = False


def _require_claude_sdk() -> None:
    if (
        not CLAUDE_AGENT_SDK_AVAILABLE
        or ClaudeSDKClient is None
        or create_sdk_mcp_server is None
        or tool is None
    ):
        raise ValueError(
            "Claude Agent support is not available because the "
            "claude-agent-sdk package is not installed."
        )


def _model_alias(model_id: str) -> str:
    if model_id.startswith(CLAUDE_AGENT_MODEL_PREFIX):
        return model_id[len(CLAUDE_AGENT_MODEL_PREFIX) :]
    return model_id


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == MessageContentTypeEnum.text.value and item.get("text"):
            parts.append(str(item["text"]).strip())
    return "\n".join(part for part in parts if part)


def _split_system_prompt(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    non_system_messages: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "")
        if role == "system":
            system_parts.append(_extract_text_content(message.get("content")))
            continue
        non_system_messages.append(message)
    return "\n\n".join(part for part in system_parts if part), non_system_messages


def _build_prompt(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user")
        name = str(message.get("name") or "").strip()
        content_text = _extract_text_content(message.get("content"))
        if not content_text and role == "tool":
            try:
                content_text = json.dumps(json.loads(str(message.get("content") or "")), indent=2)
            except (TypeError, json.JSONDecodeError):
                content_text = str(message.get("content") or "")
        if not content_text:
            continue

        if role == "tool" and name:
            heading = f"Tool ({name})"
        else:
            heading = role.capitalize()
        lines.append(f"{heading}:\n{content_text}")
    return "\n\n".join(lines).strip()


def _has_file_attachments(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == MessageContentTypeEnum.file.value:
                return True
    return False


def _resolve_effort(config: Any) -> Literal["low", "medium", "high", "max"]:
    raw_effort = str(getattr(config, "reasoning_effort", "medium") or "medium")
    if raw_effort in {"low", "medium", "high", "max"}:
        return cast(Literal["low", "medium", "high", "max"], raw_effort)
    return "medium"


def _build_thinking_config(config: Any, is_title_generation: bool) -> dict[str, str | int]:
    if is_title_generation or bool(getattr(config, "exclude_reasoning", False)):
        return {"type": "disabled"}

    effort = _resolve_effort(config)
    budget_by_effort = {
        "low": 1024,
        "medium": 2048,
        "high": 4096,
        "max": 8192,
    }
    return {"type": "enabled", "budget_tokens": budget_by_effort.get(effort, 2048)}


def _resolve_max_turns(
    req: Optional["ClaudeAgentReqChat"],
    *,
    is_title_generation: bool,
) -> int:
    if is_title_generation or req is None:
        return 1
    # Claude Code can still use its built-in sandboxed tools even when Meridian does not
    # expose any MCP tools for this request, so one turn can terminate on stop_reason=tool_use
    # before the model emits final text.
    return 4


def _has_selected_tools(req: Optional["ClaudeAgentReqChat"]) -> bool:
    return bool(req is not None and _normalize_selected_tools(req.selected_tools))


async def _allow_claude_tool_use(
    _tool_name: str,
    input_data: dict[str, Any],
    _context: Any,
):
    assert PermissionResultAllow is not None
    return PermissionResultAllow(updated_input=input_data)


async def _build_prompt_iterable(prompt: str, session_id: str):
    yield {
        "type": "user",
        "session_id": session_id,
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
    }


@dataclass
class ClaudeRuntimeContext:
    root_dir: Path
    cwd: Path
    env: dict[str, str]
    session_id: str


def _cleanup_stale_runtime_dirs() -> None:
    now = time.time()
    for runtime_dir in CLAUDE_AGENT_RUNTIME_ROOT.glob(f"{CLAUDE_AGENT_RUNTIME_PREFIX}*"):
        try:
            if not runtime_dir.is_dir():
                continue
            if is_runtime_dir_stale(
                runtime_dir,
                now=now,
                ttl_seconds=CLAUDE_AGENT_RUNTIME_TTL_SECONDS,
            ):
                shutil.rmtree(runtime_dir, ignore_errors=True)
        except Exception:
            logger.warning(
                "Failed to clean stale Claude runtime dir %s", runtime_dir, exc_info=True
            )


def _build_runtime_context(oauth_token: str) -> ClaudeRuntimeContext:
    _cleanup_stale_runtime_dirs()

    root_dir = Path(
        tempfile.mkdtemp(prefix=CLAUDE_AGENT_RUNTIME_PREFIX, dir=str(CLAUDE_AGENT_RUNTIME_ROOT))
    )
    cwd = root_dir / "workspace"
    home_dir = root_dir / "home"
    config_dir = root_dir / "config"
    data_dir = root_dir / "data"
    state_dir = root_dir / "state"
    cache_dir = root_dir / "cache"

    for directory in (
        cwd,
        home_dir,
        config_dir,
        data_dir,
        state_dir,
        cache_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    touch_runtime_heartbeat(root_dir)

    return ClaudeRuntimeContext(
        root_dir=root_dir,
        cwd=cwd,
        env={
            "CLAUDE_CODE_OAUTH_TOKEN": oauth_token,
            "HOME": str(home_dir),
            "XDG_CONFIG_HOME": str(config_dir),
            "XDG_DATA_HOME": str(data_dir),
            "XDG_STATE_HOME": str(state_dir),
            "XDG_CACHE_HOME": str(cache_dir),
        },
        session_id=str(uuid.uuid4()),
    )


def _cleanup_runtime_context(runtime_context: ClaudeRuntimeContext) -> None:
    try:
        shutil.rmtree(runtime_context.root_dir, ignore_errors=True)
    except Exception:
        logger.warning(
            "Failed to cleanup Claude runtime dir %s",
            runtime_context.root_dir,
            exc_info=True,
        )


def _build_options(
    model: str,
    oauth_token: str,
    system_prompt: str,
    config: Any,
    is_title_generation: bool,
    runtime_context: ClaudeRuntimeContext,
    req: Optional["ClaudeAgentReqChat"] = None,
    feedback_buffer: Optional[list[str]] = None,
    execution_state: Optional["ClaudeToolExecutionState"] = None,
):
    _require_claude_sdk()
    assert ClaudeAgentOptions is not None
    mcp_servers: dict[str, Any] = {}
    allowed_tools: list[str] = []
    tool_selection: list[str] = []
    permission_mode: str | None = None
    can_use_tool_callback = None
    if req is not None and feedback_buffer is not None and execution_state is not None:
        mcp_servers, allowed_tools = _build_mcp_tool_definitions(
            req, feedback_buffer, execution_state
        )
        if allowed_tools:
            # Disable Claude Code built-in tools for Meridian-managed tool runs so Claude
            # uses the request-scoped MCP wrappers instead of built-ins like WebSearch.
            tool_selection = []
            can_use_tool_callback = _allow_claude_tool_use

    return ClaudeAgentOptions(
        tools=tool_selection,
        model=_model_alias(model),
        system_prompt=system_prompt or None,
        continue_conversation=False,
        session_id=runtime_context.session_id,
        max_turns=_resolve_max_turns(req, is_title_generation=is_title_generation),
        allowed_tools=allowed_tools,
        permission_mode=cast(Any, permission_mode),
        can_use_tool=cast(Any, can_use_tool_callback),
        cwd=runtime_context.cwd,
        env=runtime_context.env,
        setting_sources=["local"],
        sandbox={
            "enabled": True,
            "autoAllowBashIfSandboxed": False,
            "excludedCommands": [],
            "allowUnsandboxedCommands": False,
            "network": {
                "allowAllUnixSockets": False,
                "allowLocalBinding": False,
            },
        },
        include_partial_messages=True,
        thinking=cast(Any, _build_thinking_config(config, is_title_generation)),
        effort=_resolve_effort(config),
        mcp_servers=mcp_servers,
    )


def _normalize_context_usage_key(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not normalized:
        return ""
    if not normalized.endswith("_tokens"):
        normalized = f"{normalized}_tokens"
    return f"context_{normalized}"


def _extract_context_usage_details(context_usage: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(context_usage, dict):
        return {}

    details: dict[str, int] = {}
    for category in context_usage.get("categories") or []:
        if not isinstance(category, dict):
            continue
        key = _normalize_context_usage_key(str(category.get("name") or ""))
        if not key:
            continue
        tokens = int(category.get("tokens", 0) or 0)
        if tokens > 0:
            details[key] = tokens

    system_prompt_tokens = 0
    for section in context_usage.get("systemPromptSections") or []:
        if not isinstance(section, dict):
            continue
        system_prompt_tokens += int(section.get("tokens", 0) or 0)
    if system_prompt_tokens > 0:
        details["context_system_prompt_tokens"] = system_prompt_tokens

    return details


async def _get_context_usage_snapshot(client: Any) -> dict[str, Any] | None:
    try:
        context_usage = await client.get_context_usage()
    except Exception:
        logger.warning("Failed to fetch Claude context usage snapshot", exc_info=True)
        return None

    if isinstance(context_usage, dict):
        return context_usage
    return None


def _normalize_usage(
    usage: dict[str, Any], context_usage: dict[str, Any] | None = None
) -> dict[str, Any]:
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
    cache_read_input_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
    prompt_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
    prompt_tokens_details = {
        "input_tokens": input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
    }
    prompt_tokens_details.update(_extract_context_usage_details(context_usage))

    return {
        "cost": 0.0,
        "is_byok": True,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "prompt_tokens_details": prompt_tokens_details,
        "completion_tokens_details": {},
    }


def _normalize_tool_storage_value(tool_value: Any) -> Any:
    try:
        json.dumps(tool_value)
        return tool_value
    except TypeError:
        return {"value": str(tool_value)}


def _extract_stream_delta(event: dict[str, Any], *, thinking_started: bool) -> tuple[str, bool]:
    event_type = str(event.get("type") or "")
    if event_type != "content_block_delta":
        return "", thinking_started

    delta = event.get("delta")
    if not isinstance(delta, dict):
        return "", thinking_started

    delta_type = str(delta.get("type") or "")
    if delta_type == "thinking_delta":
        prefix = "[THINK]\n" if not thinking_started else ""
        return f"{prefix}{str(delta.get('thinking') or '')}", True
    if delta_type == "text_delta":
        prefix = "\n[!THINK]\n" if thinking_started else ""
        return f"{prefix}{str(delta.get('text') or '')}", False

    return "", thinking_started


CLAUDE_TOOL_NAME_BY_ENUM: dict[ToolEnum, str] = {
    ToolEnum.WEB_SEARCH: "web_search",
    ToolEnum.LINK_EXTRACTION: "fetch_page_content",
    ToolEnum.EXECUTE_CODE: "execute_code",
    ToolEnum.IMAGE_GENERATION: "generate_image",
    ToolEnum.VISUALISE: "visualise",
    ToolEnum.ASK_USER: "ask_user",
}
CLAUDE_SUPPORTED_TOOLS = set(CLAUDE_TOOL_NAME_BY_ENUM)


@dataclass
class ClaudePendingAskUserState:
    public_tool_call_id: str
    arguments: dict[str, Any]


@dataclass
class ClaudeToolExecutionState:
    pending_ask_user: ClaudePendingAskUserState | None = None
    continuation_messages: list[dict[str, Any]] = field(default_factory=list)


def _normalize_selected_tools(selected_tools: list[Any] | None) -> list[ToolEnum]:
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


def _drain_feedback_buffer(buffer: list[str]) -> list[str]:
    drained = list(buffer)
    buffer.clear()
    return drained


def _serialize_sandbox_input_files(input_files: list[Any]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for input_file in input_files:
        if not input_file:
            continue
        serialized.append(
            {
                "file_id": str(getattr(input_file, "file_id", "") or ""),
                "storage_path": str(getattr(input_file, "storage_path", "") or ""),
                "relative_path": str(getattr(input_file, "relative_path", "") or ""),
                "name": str(getattr(input_file, "name", "") or ""),
                "content_type": str(
                    getattr(input_file, "content_type", "application/octet-stream")
                    or "application/octet-stream"
                ),
                "size": int(getattr(input_file, "size", 0) or 0),
            }
        )
    return serialized


async def _persist_pending_tool_continuation(
    redis_manager: RedisManager,
    *,
    public_tool_call_id: str,
    req: "ClaudeAgentReqChat",
    messages: list[dict[str, Any]],
) -> None:
    await redis_manager.set_pending_tool_continuation(
        public_tool_call_id,
        {
            "messages": messages,
            "model": req.model,
            "model_id": req.model_id,
            "config": req.config.model_dump(mode="json"),
            "user_id": req.user_id,
            "node_id": req.node_id,
            "graph_id": req.graph_id,
            "node_type": req.node_type.value,
            "file_hashes": req.file_hashes,
            "pdf_engine": req.pdf_engine,
            "selected_tools": [
                tool.value for tool in _normalize_selected_tools(req.selected_tools)
            ],
            "sandbox_input_files": _serialize_sandbox_input_files(req.sandbox_input_files or []),
            "sandbox_input_warnings": req.sandbox_input_warnings,
        },
    )


def _format_result_error(message: ResultMessage) -> str:
    parts: list[str] = []
    if message.result:
        parts.append(str(message.result))
    if message.errors:
        parts.extend(str(error) for error in message.errors if error)
    if message.permission_denials:
        parts.append(f"permission_denials={message.permission_denials}")
    if message.stop_reason:
        parts.append(f"stop_reason={message.stop_reason}")
    return " | ".join(part for part in parts if part) or "Claude Agent request failed."


async def _persist_claude_tool_call(
    *,
    req: "ClaudeAgentReqChat",
    tool_name: str,
    arguments: dict[str, Any],
    tool_result: Any,
    duration_ms: int | None,
) -> str:
    public_tool_call_id = str(uuid.uuid4())
    if not req.graph_id or not req.node_id or not req.user_id:
        return public_tool_call_id

    normalized_result = _normalize_tool_storage_value(tool_result)
    model_context_payload = json.dumps(normalized_result, separators=(",", ":"))

    try:
        persisted_tool_call = await create_tool_call(
            req.pg_engine,
            user_id=req.user_id,
            graph_id=req.graph_id,
            node_id=req.node_id,
            model_id=req.model_id,
            tool_call_id=None,
            tool_name=tool_name,
            status=resolve_tool_status(tool_result),
            duration_ms=duration_ms,
            arguments=_normalize_tool_storage_value(arguments),
            result=normalized_result,
            model_context_payload=model_context_payload,
        )
        if persisted_tool_call.id is not None:
            public_tool_call_id = str(persisted_tool_call.id)
    except Exception:
        logger.warning(
            "Failed to persist Claude tool call %s for node %s",
            tool_name,
            req.node_id,
            exc_info=True,
        )

    return public_tool_call_id


async def _execute_claude_tool(
    *,
    req: "ClaudeAgentReqChat",
    runtime_name: str,
    arguments: dict[str, Any],
    feedback_buffer: list[str],
    execution_state: ClaudeToolExecutionState,
) -> dict[str, Any]:
    runtime = get_tool_runtime(runtime_name)
    if runtime is None:
        tool_result: Any = {"error": f"Unknown tool: {runtime_name}"}
        duration_ms = 0
    else:
        started_at = time.perf_counter()
        try:
            tool_result = await runtime.handler(arguments, req)
        except Exception as exc:
            tool_result = {"error": f"Tool execution failed: {exc}"}
        duration_ms = int((time.perf_counter() - started_at) * 1000)

    if runtime_name == ToolEnum.ASK_USER.value:
        pending_result = AskUserPendingResult().model_dump()
        pending_payload = json.dumps(pending_result, separators=(",", ":"))
        public_tool_call_id = str(uuid.uuid4())
        if req.graph_id and req.node_id and req.user_id:
            try:
                persisted_tool_call = await create_tool_call(
                    req.pg_engine,
                    user_id=req.user_id,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    model_id=req.model_id,
                    tool_call_id=None,
                    tool_name=runtime_name,
                    status=ToolCallStatusEnum.PENDING_USER_INPUT,
                    duration_ms=duration_ms,
                    arguments=_normalize_tool_storage_value(tool_result),
                    result=pending_result,
                    model_context_payload=pending_payload,
                )
                if persisted_tool_call.id is not None:
                    public_tool_call_id = str(persisted_tool_call.id)
            except Exception:
                logger.warning(
                    "Failed to persist pending Claude ask_user call for node %s",
                    req.node_id,
                    exc_info=True,
                )
        if runtime is not None:
            feedback_buffer.append(
                runtime.summary_renderer(
                    public_tool_call_id,
                    cast(dict[str, Any], tool_result),
                    pending_result,
                    duration_ms,
                )
            )
        execution_state.pending_ask_user = ClaudePendingAskUserState(
            public_tool_call_id=public_tool_call_id,
            arguments=cast(dict[str, Any], tool_result),
        )
        return {
            "content": [{"type": "text", "text": pending_payload}],
            "is_error": False,
        }

    public_tool_call_id = await _persist_claude_tool_call(
        req=req,
        tool_name=runtime_name,
        arguments=arguments,
        tool_result=tool_result,
        duration_ms=duration_ms,
    )
    if runtime is not None:
        feedback_buffer.append(
            runtime.summary_renderer(public_tool_call_id, arguments, tool_result, duration_ms)
        )

    normalized_result = _normalize_tool_storage_value(tool_result)
    execution_state.continuation_messages.append(
        {
            "role": "tool",
            "name": runtime_name,
            "content": json.dumps(normalized_result, separators=(",", ":"), ensure_ascii=True),
        }
    )
    return {
        "content": [{"type": "text", "text": json.dumps(normalized_result, ensure_ascii=True)}],
        "is_error": resolve_tool_status(tool_result) == ToolCallStatusEnum.ERROR,
    }


def _build_mcp_tool_definitions(
    req: "ClaudeAgentReqChat",
    feedback_buffer: list[str],
    execution_state: ClaudeToolExecutionState,
) -> tuple[dict[str, Any], list[str]]:
    _require_claude_sdk()
    assert create_sdk_mcp_server is not None
    assert tool is not None

    selected_tools = _normalize_selected_tools(req.selected_tools)
    runtime_names = [
        CLAUDE_TOOL_NAME_BY_ENUM[selected_tool]
        for selected_tool in selected_tools
        if selected_tool in CLAUDE_TOOL_NAME_BY_ENUM
    ]
    if not runtime_names:
        return {}, []

    sdk_tools: list[Any] = []
    allowed_tools: list[str] = []
    for runtime_name in runtime_names:
        runtime = get_tool_runtime(runtime_name)
        if runtime is None or not runtime.tool_definitions:
            continue

        definition = runtime.tool_definitions[0].get("function", {})
        name = str(definition.get("name") or runtime_name)
        description = str(definition.get("description") or runtime_name)
        input_schema = cast(
            dict[str, Any],
            definition.get("parameters") or {"type": "object", "properties": {}},
        )

        @tool(name, description, input_schema)
        async def wrapped_tool(
            arguments: dict[str, Any],
            *,
            runtime_name: str = runtime_name,
        ) -> dict[str, Any]:
            return await _execute_claude_tool(
                req=req,
                runtime_name=runtime_name,
                arguments=arguments,
                feedback_buffer=feedback_buffer,
                execution_state=execution_state,
            )

        sdk_tools.append(wrapped_tool)
        allowed_tools.append(name)

    if not sdk_tools:
        return {}, []

    return {"meridian": create_sdk_mcp_server("meridian", tools=sdk_tools)}, allowed_tools


@dataclass
class ClaudeAgentReqChat:
    oauth_token: str
    model: str
    messages: list[Message] | list[dict[str, Any]]
    config: Any
    user_id: str
    pg_engine: SQLAlchemyAsyncEngine
    model_id: Optional[str] = None
    node_id: Optional[str] = None
    graph_id: Optional[str] = None
    is_title_generation: bool = False
    node_type: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT
    schema: Optional[type[Any]] = None
    stream: bool = True
    file_uuids: Optional[list[str]] = None
    file_hashes: Optional[dict[str, str]] = None
    pdf_engine: str = "default"
    selected_tools: Optional[list[Any]] = None
    sandbox_input_files: Optional[list[Any]] = None
    sandbox_input_warnings: Optional[list[str]] = None
    http_client: Any = None

    def __post_init__(self) -> None:
        self.messages = [
            message.model_dump(exclude_none=True) if isinstance(message, Message) else message
            for message in self.messages
        ]
        self.selected_tools = self.selected_tools or []
        self.file_uuids = self.file_uuids or []
        self.file_hashes = self.file_hashes or {}
        self.sandbox_input_files = self.sandbox_input_files or []
        self.sandbox_input_warnings = self.sandbox_input_warnings or []

    def validate_request(self) -> None:
        _require_claude_sdk()
        if self.schema is not None:
            raise ValueError("Claude Agent models do not support structured-output helpers yet.")
        selected_tools = _normalize_selected_tools(self.selected_tools)
        unsupported_tools = [
            tool.value for tool in selected_tools if tool not in CLAUDE_SUPPORTED_TOOLS
        ]
        if unsupported_tools:
            unsupported = ", ".join(unsupported_tools)
            raise ValueError(
                "Claude Agent models currently support only these Meridian tools: "
                "web_search, link_extraction, execute_code, image_generation, visualise, ask_user. "
                f"Unsupported selection: {unsupported}."
            )
        if (
            self.file_uuids
            or self.file_hashes
            or _has_file_attachments(cast(list[dict[str, Any]], self.messages))
        ):
            raise ValueError("Claude Agent models do not support attachments or PDF parsing yet.")
        if self.http_client is None and any(
            tool
            in {
                ToolEnum.WEB_SEARCH,
                ToolEnum.EXECUTE_CODE,
                ToolEnum.IMAGE_GENERATION,
                ToolEnum.VISUALISE,
            }
            for tool in selected_tools
        ):
            raise ValueError("Claude Agent tool execution requires an HTTP client in this request.")


async def validate_claude_agent_token(token: str) -> None:
    _require_claude_sdk()
    assert ClaudeSDKClient is not None

    runtime_context = _build_runtime_context(token)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    try:
        options = _build_options(
            model=f"{CLAUDE_AGENT_MODEL_PREFIX}default",
            oauth_token=token,
            system_prompt="Reply with OK.",
            config=SimpleNamespace(exclude_reasoning=True, reasoning_effort="low"),
            is_title_generation=True,
            runtime_context=runtime_context,
        )
        async with ClaudeSDKClient(options) as client:
            await client.query("Reply with OK.", session_id=runtime_context.session_id)
            async for message in client.receive_response():
                if (
                    ResultMessage is not None
                    and isinstance(message, ResultMessage)
                    and message.is_error
                ):
                    raise ValueError(_format_result_error(message))
    finally:
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)


async def make_claude_agent_request_non_streaming(
    req: ClaudeAgentReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    _require_claude_sdk()
    if ToolEnum.ASK_USER in _normalize_selected_tools(req.selected_tools):
        raise ValueError("Claude Agent ask_user requires streaming mode.")
    assert ClaudeSDKClient is not None

    system_prompt, prompt_messages = _split_system_prompt(cast(list[dict[str, Any]], req.messages))
    prompt = _build_prompt(prompt_messages)
    response_text = ""
    final_usage: Optional[dict[str, Any]] = None
    raw_final_usage: Optional[dict[str, Any]] = None
    tool_feedback_buffer: list[str] = []
    execution_state = ClaudeToolExecutionState()
    runtime_context = _build_runtime_context(req.oauth_token)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)

    try:
        options = _build_options(
            req.model,
            req.oauth_token,
            system_prompt,
            req.config,
            req.is_title_generation,
            runtime_context,
            req=req,
            feedback_buffer=tool_feedback_buffer,
            execution_state=execution_state,
        )

        with sentry_sdk.start_span(op="ai.request", description="Claude Agent request") as span:
            span.set_tag("chat.model", req.model)
            prompt_input: Any = (
                _build_prompt_iterable(prompt, runtime_context.session_id)
                if _has_selected_tools(req)
                else prompt
            )
            async with ClaudeSDKClient(options) as client:
                await client.query(prompt_input, session_id=runtime_context.session_id)
                async for message in client.receive_response():
                    if AssistantMessage is not None and isinstance(message, AssistantMessage):
                        for block in message.content:
                            if TextBlock is not None and isinstance(block, TextBlock):
                                response_text += block.text
                    elif ResultMessage is not None and isinstance(message, ResultMessage):
                        if message.is_error:
                            raise ValueError(_format_result_error(message))
                        if message.usage:
                            raw_final_usage = message.usage

                if raw_final_usage:
                    final_usage = _normalize_usage(
                        raw_final_usage,
                        await _get_context_usage_snapshot(client),
                    )

            if final_usage and req.graph_id and req.node_id and not req.is_title_generation:
                await update_node_usage_data(
                    pg_engine=pg_engine,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    usage_data=final_usage,
                    node_type=req.node_type,
                    model_id=req.model_id,
                )
    finally:
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)

    return "".join(tool_feedback_buffer) + response_text


async def stream_claude_agent_response(
    req: ClaudeAgentReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()
    _require_claude_sdk()
    assert ClaudeSDKClient is not None

    system_prompt, prompt_messages = _split_system_prompt(cast(list[dict[str, Any]], req.messages))
    prompt = _build_prompt(prompt_messages)
    model_output_emitted = False
    thinking_started = False
    final_usage: Optional[dict[str, Any]] = None
    raw_final_usage: Optional[dict[str, Any]] = None
    awaiting_user_input = False
    tool_feedback_buffer: list[str] = []
    execution_state = ClaudeToolExecutionState()
    runtime_context = _build_runtime_context(req.oauth_token)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    try:
        options = _build_options(
            req.model,
            req.oauth_token,
            system_prompt,
            req.config,
            req.is_title_generation,
            runtime_context,
            req=req,
            feedback_buffer=tool_feedback_buffer,
            execution_state=execution_state,
        )

        with sentry_sdk.start_span(op="ai.streaming", description="Claude Agent stream") as span:
            span.set_tag("chat.model", req.model)
            prompt_input: Any = (
                _build_prompt_iterable(prompt, runtime_context.session_id)
                if _has_selected_tools(req)
                else prompt
            )
            async with ClaudeSDKClient(options) as client:
                await client.query(prompt_input, session_id=runtime_context.session_id)
                async for message in client.receive_response():
                    for feedback in _drain_feedback_buffer(tool_feedback_buffer):
                        yield feedback
                    if execution_state.pending_ask_user is not None:
                        await _persist_pending_tool_continuation(
                            redis_manager,
                            public_tool_call_id=(
                                execution_state.pending_ask_user.public_tool_call_id
                            ),
                            req=req,
                            messages=[
                                *cast(list[dict[str, Any]], req.messages),
                                *execution_state.continuation_messages,
                            ],
                        )
                        if final_data_container is not None:
                            final_data_container["pending_tool_call_id"] = (
                                execution_state.pending_ask_user.public_tool_call_id
                            )
                        awaiting_user_input = True
                        break
                    if StreamEvent is not None and isinstance(message, StreamEvent):
                        chunk, thinking_started = _extract_stream_delta(
                            message.event, thinking_started=thinking_started
                        )
                        if chunk:
                            model_output_emitted = True
                            yield chunk
                    elif AssistantMessage is not None and isinstance(message, AssistantMessage):
                        if model_output_emitted:
                            continue
                        for block in message.content:
                            if (
                                ThinkingBlock is not None
                                and isinstance(block, ThinkingBlock)
                                and block.thinking
                            ):
                                prefix = "[THINK]\n" if not thinking_started else ""
                                model_output_emitted = True
                                thinking_started = True
                                yield f"{prefix}{block.thinking}"
                            elif (
                                TextBlock is not None
                                and isinstance(block, TextBlock)
                                and block.text
                            ):
                                prefix = "\n[!THINK]\n" if thinking_started else ""
                                model_output_emitted = True
                                thinking_started = False
                                yield f"{prefix}{block.text}"
                    elif ResultMessage is not None and isinstance(message, ResultMessage):
                        if message.is_error:
                            raise ValueError(_format_result_error(message))
                        if message.usage:
                            raw_final_usage = message.usage

                if raw_final_usage:
                    final_usage = _normalize_usage(
                        raw_final_usage,
                        await _get_context_usage_snapshot(client),
                    )

        if execution_state.pending_ask_user is not None and not awaiting_user_input:
            await _persist_pending_tool_continuation(
                redis_manager,
                public_tool_call_id=execution_state.pending_ask_user.public_tool_call_id,
                req=req,
                messages=[
                    *cast(list[dict[str, Any]], req.messages),
                    *execution_state.continuation_messages,
                ],
            )
            if final_data_container is not None:
                final_data_container["pending_tool_call_id"] = (
                    execution_state.pending_ask_user.public_tool_call_id
                )
            awaiting_user_input = True
    finally:
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)

    for feedback in _drain_feedback_buffer(tool_feedback_buffer):
        yield feedback

    if thinking_started:
        yield "\n[!THINK]\n"

    if (
        final_usage
        and not awaiting_user_input
        and not req.is_title_generation
        and final_data_container is not None
    ):
        final_data_container["usage_data"] = final_usage

    if (
        final_usage
        and not awaiting_user_input
        and req.graph_id
        and req.node_id
        and not req.is_title_generation
    ):
        await update_node_usage_data(
            pg_engine=pg_engine,
            graph_id=req.graph_id,
            node_id=req.node_id,
            usage_data=final_usage,
            node_type=req.node_type,
            model_id=req.model_id,
        )
