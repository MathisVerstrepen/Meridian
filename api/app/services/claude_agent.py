import json
import logging
import re
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator, Literal, Optional, cast

import sentry_sdk
from database.pg.chat_ops import create_tool_call
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.models import ToolCallStatusEnum
from database.redis.redis_ops import RedisManager
from models.message import ToolEnum
from models.tool_question import AskUserPendingResult
from services.provider_runtime import (
    build_runtime_directory_layout,
    cleanup_runtime_dir,
    start_runtime_heartbeat,
    stop_runtime_heartbeat,
)
from services.providers.claude_agent_catalog import CLAUDE_AGENT_MODEL_PREFIX
from services.providers.common import (
    BaseProviderReq,
    ThinkingState,
    build_prompt,
    has_file_attachments,
    normalize_selected_tools,
    normalize_tool_storage_value,
    split_system_prompt,
    strip_model_prefix,
    validate_http_client_for_tools,
    validate_supported_tools,
)
from services.providers.tool_continuation import persist_pending_tool_continuation
from services.tools import get_tool_runtime, resolve_tool_status
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")
CLAUDE_AGENT_RUNTIME_PREFIX = "meridian-claude-agent-"
CLAUDE_AGENT_RUNTIME_ROOT = Path(tempfile.gettempdir())
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
    return bool(req is not None and normalize_selected_tools(req.selected_tools))


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


def _build_runtime_context(oauth_token: str) -> ClaudeRuntimeContext:
    layout = build_runtime_directory_layout(
        CLAUDE_AGENT_RUNTIME_ROOT,
        prefix=CLAUDE_AGENT_RUNTIME_PREFIX,
        ttl_seconds=CLAUDE_AGENT_RUNTIME_TTL_SECONDS,
        provider_label="Claude",
    )

    return ClaudeRuntimeContext(
        root_dir=layout.root_dir,
        cwd=layout.cwd,
        env={
            "CLAUDE_CODE_OAUTH_TOKEN": oauth_token,
            "HOME": str(layout.home_dir),
            "XDG_CONFIG_HOME": str(layout.config_dir),
            "XDG_DATA_HOME": str(layout.data_dir),
            "XDG_STATE_HOME": str(layout.state_dir),
            "XDG_CACHE_HOME": str(layout.cache_dir),
        },
        session_id=str(uuid.uuid4()),
    )


def _cleanup_runtime_context(runtime_context: ClaudeRuntimeContext) -> None:
    cleanup_runtime_dir(runtime_context.root_dir, provider_label="Claude")


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
        model=strip_model_prefix(model, CLAUDE_AGENT_MODEL_PREFIX),
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


@dataclass
class ClaudePendingAskUserState:
    public_tool_call_id: str
    arguments: dict[str, Any]


@dataclass
class ClaudeToolExecutionState:
    pending_ask_user: ClaudePendingAskUserState | None = None
    continuation_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ClaudeToolCallRecord:
    tool_name: str
    arguments: dict[str, Any]
    persisted_result: Any
    rendered_result: Any
    model_context_payload: str
    status: ToolCallStatusEnum
    duration_ms: int | None


def _drain_feedback_buffer(buffer: list[str]) -> list[str]:
    drained = list(buffer)
    buffer.clear()
    return drained


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
    record: ClaudeToolCallRecord,
) -> str:
    public_tool_call_id = str(uuid.uuid4())
    if not req.graph_id or not req.node_id or not req.user_id:
        return public_tool_call_id

    try:
        persisted_tool_call = await create_tool_call(
            req.pg_engine,
            user_id=req.user_id,
            graph_id=req.graph_id,
            node_id=req.node_id,
            model_id=req.model_id,
            tool_call_id=None,
            tool_name=record.tool_name,
            status=record.status,
            duration_ms=record.duration_ms,
            arguments=normalize_tool_storage_value(record.arguments),
            result=record.persisted_result,
            model_context_payload=record.model_context_payload,
        )
        if persisted_tool_call.id is not None:
            public_tool_call_id = str(persisted_tool_call.id)
    except Exception:
        logger.warning(
            "Failed to persist Claude tool call %s for node %s",
            record.tool_name,
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

    normalized_result = normalize_tool_storage_value(tool_result)
    status = resolve_tool_status(tool_result)
    model_context_payload = json.dumps(normalized_result, separators=(",", ":"))
    record = ClaudeToolCallRecord(
        tool_name=runtime_name,
        arguments=arguments,
        persisted_result=normalized_result,
        rendered_result=tool_result,
        model_context_payload=model_context_payload,
        status=status,
        duration_ms=duration_ms,
    )

    if runtime_name == ToolEnum.ASK_USER.value:
        pending_result = AskUserPendingResult().model_dump()
        pending_payload = json.dumps(pending_result, separators=(",", ":"))
        record = ClaudeToolCallRecord(
            tool_name=runtime_name,
            arguments=cast(dict[str, Any], tool_result),
            persisted_result=pending_result,
            rendered_result=pending_result,
            model_context_payload=pending_payload,
            status=ToolCallStatusEnum.PENDING_USER_INPUT,
            duration_ms=duration_ms,
        )
        public_tool_call_id = await _persist_claude_tool_call(req=req, record=record)
        if runtime is not None:
            feedback_buffer.append(
                runtime.summary_renderer(
                    public_tool_call_id,
                    cast(dict[str, Any], tool_result),
                    record.rendered_result,
                    duration_ms,
                )
            )
        execution_state.pending_ask_user = ClaudePendingAskUserState(
            public_tool_call_id=public_tool_call_id,
            arguments=cast(dict[str, Any], tool_result),
        )
        return {
            "content": [{"type": "text", "text": record.model_context_payload}],
            "is_error": False,
        }

    public_tool_call_id = await _persist_claude_tool_call(req=req, record=record)
    if runtime is not None:
        feedback_buffer.append(
            runtime.summary_renderer(
                public_tool_call_id,
                record.arguments,
                record.rendered_result,
                duration_ms,
            )
        )

    execution_state.continuation_messages.append(
        {
            "role": "tool",
            "name": runtime_name,
            "content": record.model_context_payload,
        }
    )
    return {
        "content": [{"type": "text", "text": record.model_context_payload}],
        "is_error": record.status == ToolCallStatusEnum.ERROR,
    }


def _build_mcp_tool_definitions(
    req: "ClaudeAgentReqChat",
    feedback_buffer: list[str],
    execution_state: ClaudeToolExecutionState,
) -> tuple[dict[str, Any], list[str]]:
    _require_claude_sdk()
    assert create_sdk_mcp_server is not None
    assert tool is not None

    selected_tools = normalize_selected_tools(req.selected_tools)
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


@dataclass(kw_only=True)
class ClaudeAgentReqChat(BaseProviderReq):
    oauth_token: str

    def __post_init__(self) -> None:
        super().__post_init__()

    def validate_request(self) -> None:
        _require_claude_sdk()
        if self.schema is not None:
            raise ValueError("Claude Agent models do not support structured-output helpers yet.")
        validate_supported_tools("Claude Agent", self.selected_tools)
        if (
            self.file_uuids
            or self.file_hashes
            or has_file_attachments(cast(list[dict[str, Any]], self.messages))
        ):
            raise ValueError("Claude Agent models do not support attachments or PDF parsing yet.")
        validate_http_client_for_tools("Claude Agent", self.selected_tools, self.http_client)


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
    if ToolEnum.ASK_USER in normalize_selected_tools(req.selected_tools):
        raise ValueError("Claude Agent ask_user requires streaming mode.")
    assert ClaudeSDKClient is not None

    system_prompt, prompt_messages = split_system_prompt(cast(list[dict[str, Any]], req.messages))
    prompt = build_prompt(prompt_messages)
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

    system_prompt, prompt_messages = split_system_prompt(cast(list[dict[str, Any]], req.messages))
    prompt = build_prompt(prompt_messages)
    model_output_emitted = False
    thinking_state = ThinkingState()
    final_usage: Optional[dict[str, Any]] = None
    raw_final_usage: Optional[dict[str, Any]] = None
    awaiting_user_input = False
    tool_feedback_buffer: list[str] = []
    execution_state = ClaudeToolExecutionState()
    runtime_context = _build_runtime_context(req.oauth_token)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)

    async def _flush_tool_feedback() -> AsyncIterator[str]:
        buffered_feedback = _drain_feedback_buffer(tool_feedback_buffer)
        if not buffered_feedback:
            return
        closing_chunk = thinking_state.close_chunk()
        if closing_chunk:
            yield closing_chunk
        for feedback in buffered_feedback:
            yield feedback

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
                    async for feedback in _flush_tool_feedback():
                        yield feedback
                    if execution_state.pending_ask_user is not None:
                        await persist_pending_tool_continuation(
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
                            message.event, thinking_started=thinking_state.is_open
                        )
                        thinking_state.is_open = thinking_started
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
                                prefix = thinking_state.open_chunk()
                                model_output_emitted = True
                                yield f"{prefix}{block.thinking}"
                            elif (
                                TextBlock is not None
                                and isinstance(block, TextBlock)
                                and block.text
                            ):
                                prefix = thinking_state.close_chunk()
                                model_output_emitted = True
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
            await persist_pending_tool_continuation(
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

    async for feedback in _flush_tool_feedback():
        yield feedback

    closing_chunk = thinking_state.close_chunk()
    if closing_chunk:
        yield closing_chunk

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
