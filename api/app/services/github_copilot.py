import asyncio
import contextlib
import hashlib
import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Optional, cast

from database.pg.chat_ops import create_tool_call
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.models import ToolCallStatusEnum
from database.redis.redis_ops import RedisManager
from models.inference import ModelInfo
from models.message import MessageContentTypeEnum, NodeTypeEnum, ToolEnum
from models.tool_question import AskUserPendingResult
from pydantic import BaseModel
from services.provider_runtime import (
    is_runtime_dir_stale,
    start_runtime_heartbeat,
    stop_runtime_heartbeat,
    touch_runtime_heartbeat,
)
from services.providers.github_copilot_catalog import (
    GITHUB_COPILOT_MODEL_PREFIX,
    GITHUB_COPILOT_SUPPORTED_TOOL_NAMES,
    normalize_github_copilot_model,
)
from services.sandbox_inputs import SandboxInputFileReference
from services.tools import (
    TOOL_HANDLERS_BY_NAME,
    get_openrouter_tools,
    get_tool_runtime,
    resolve_tool_status,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

GITHUB_COPILOT_RUNTIME_PREFIX = "meridian-github-copilot-"
GITHUB_COPILOT_RUNTIME_ROOT = Path("/tmp")
GITHUB_COPILOT_RUNTIME_TTL_SECONDS = 60 * 60  # 1 hour
GITHUB_COPILOT_MODEL_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
GITHUB_COPILOT_SYSTEM_PROMPT_SECTION_IDS = (
    "identity",
    "tone",
    "tool_efficiency",
    "environment_context",
    "code_change_rules",
    "guidelines",
    "safety",
    "tool_instructions",
    "custom_instructions",
    "last_instructions",
)
ASK_USER_TOOL_NAME = ToolEnum.ASK_USER.value
ASK_USER_BATCH_ERROR = (
    "ask_user must be the only interactive tool call in a tool round. "
    "Ask one question at a time and wait for the user response before requesting more tools."
)
GITHUB_COPILOT_SUPPORTED_TOOLS = {
    ToolEnum.WEB_SEARCH,
    ToolEnum.LINK_EXTRACTION,
    ToolEnum.EXECUTE_CODE,
    ToolEnum.IMAGE_GENERATION,
    ToolEnum.VISUALISE,
    ToolEnum.ASK_USER,
}
_GITHUB_COPILOT_MODEL_CACHE: dict[str, tuple[float, list[ModelInfo]]] = {}


@dataclass
class GitHubCopilotPendingAskUserState:
    public_tool_call_id: str


@dataclass
class GitHubCopilotToolExecutionState:
    pending_ask_user: GitHubCopilotPendingAskUserState | None = None
    continuation_messages: list[dict[str, Any]] = field(default_factory=list)


try:
    from copilot import CopilotClient, SubprocessConfig
    from copilot.session import PermissionHandler
    from copilot.tools import Tool, ToolInvocation, ToolResult

    GITHUB_COPILOT_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when SDK missing
    CopilotClient = None  # type: ignore[misc,assignment]
    SubprocessConfig = None  # type: ignore[misc,assignment]
    PermissionHandler = None  # type: ignore[misc,assignment]
    Tool = None  # type: ignore[misc,assignment]
    ToolInvocation = None  # type: ignore[misc,assignment]
    ToolResult = None  # type: ignore[misc,assignment]
    GITHUB_COPILOT_SDK_AVAILABLE = False


def _require_github_copilot_sdk() -> None:
    if not GITHUB_COPILOT_SDK_AVAILABLE or CopilotClient is None or SubprocessConfig is None:
        raise ValueError(
            "GitHub Copilot support is not available because the github-copilot-sdk package "
            "is not installed."
        )


def _model_alias(model_id: str) -> str:
    if model_id.startswith(GITHUB_COPILOT_MODEL_PREFIX):
        return model_id[len(GITHUB_COPILOT_MODEL_PREFIX) :]
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


def _split_system_prompt(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
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

        heading = f"Tool ({name})" if role == "tool" and name else role.capitalize()
        lines.append(f"{heading}:\n{content_text}")
    return "\n\n".join(lines).strip()


def _has_file_attachments(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == MessageContentTypeEnum.file.value:
                return True
    return False


def _has_image_inputs(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") == MessageContentTypeEnum.image_url.value
            ):
                return True
    return False


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


def _normalize_tool_storage_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _normalize_tool_storage_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_tool_storage_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _serialize_sandbox_input_files(
    input_files: list[SandboxInputFileReference],
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


def _normalize_reasoning_effort(
    config: Any,
    is_title_generation: bool,
) -> Literal["low", "medium", "high", "xhigh"] | None:
    if is_title_generation or bool(getattr(config, "exclude_reasoning", False)):
        return None

    raw_effort = str(getattr(config, "reasoning_effort", "") or "").strip().lower()
    if raw_effort == "low":
        return "low"
    if raw_effort == "medium":
        return "medium"
    if raw_effort == "high":
        return "high"
    if raw_effort in {"max", "xhigh"}:
        return "xhigh"
    return None


def _normalize_usage_data(event_data: Any) -> dict[str, Any] | None:
    input_tokens = int(getattr(event_data, "input_tokens", 0) or 0)
    output_tokens = int(getattr(event_data, "output_tokens", 0) or 0)
    cache_read_tokens = int(getattr(event_data, "cache_read_tokens", 0) or 0)
    cache_write_tokens = int(getattr(event_data, "cache_write_tokens", 0) or 0)
    cost = float(getattr(event_data, "cost", 0.0) or 0.0)

    copilot_usage = getattr(event_data, "copilot_usage", None)
    if copilot_usage is not None:
        for token_detail in getattr(copilot_usage, "token_details", []) or []:
            token_type = str(getattr(token_detail, "token_type", "") or "").strip().lower()
            token_count = int(getattr(token_detail, "token_count", 0) or 0)
            if token_type == "input" and not input_tokens:
                input_tokens = token_count
            elif token_type == "output" and not output_tokens:
                output_tokens = token_count
        total_nano_aiu = float(getattr(copilot_usage, "total_nano_aiu", 0.0) or 0.0)
        if not cost and total_nano_aiu:
            cost = total_nano_aiu / 1_000_000_000

    total_tokens = int(getattr(event_data, "total_tokens", 0) or 0) or (
        input_tokens + output_tokens
    )

    if not total_tokens and not cost and not cache_read_tokens and not cache_write_tokens:
        return None

    return {
        "cost": cost,
        "is_byok": False,
        "total_tokens": total_tokens,
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "prompt_tokens_details": {
            "cache_read_tokens": cache_read_tokens,
            "cache_write_tokens": cache_write_tokens,
        },
        "completion_tokens_details": {},
    }


def _merge_usage_data(
    existing_usage: dict[str, Any] | None,
    new_usage: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if new_usage is None:
        return existing_usage
    if existing_usage is None:
        return new_usage

    prompt_tokens = max(
        int(existing_usage.get("prompt_tokens", 0) or 0),
        int(new_usage.get("prompt_tokens", 0) or 0),
    )
    completion_tokens = max(
        int(existing_usage.get("completion_tokens", 0) or 0),
        int(new_usage.get("completion_tokens", 0) or 0),
    )
    total_tokens = max(
        int(existing_usage.get("total_tokens", 0) or 0),
        int(new_usage.get("total_tokens", 0) or 0),
        prompt_tokens + completion_tokens,
    )
    prompt_tokens_details = dict(existing_usage.get("prompt_tokens_details", {}) or {})
    for key, value in dict(new_usage.get("prompt_tokens_details", {}) or {}).items():
        prompt_tokens_details[key] = max(
            int(prompt_tokens_details.get(key, 0) or 0), int(value or 0)
        )

    completion_tokens_details = dict(existing_usage.get("completion_tokens_details", {}) or {})
    for key, value in dict(new_usage.get("completion_tokens_details", {}) or {}).items():
        completion_tokens_details[key] = max(
            int(completion_tokens_details.get(key, 0) or 0),
            int(value or 0),
        )

    return {
        "cost": 0.0,
        "is_byok": False,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_tokens_details": prompt_tokens_details,
        "completion_tokens_details": completion_tokens_details,
    }


def _build_copilot_system_message(
    system_prompt: str,
    available_tool_names: list[str],
) -> dict[str, Any]:
    available_tools_text = ", ".join(available_tool_names) if available_tool_names else "none"
    authoritative_prompt = system_prompt.strip()
    if authoritative_prompt:
        authoritative_prompt += "\n\n"
    authoritative_prompt += (
        "Session-specific Meridian constraints:\n"
        "- Treat this Meridian prompt as the authoritative instruction set for this session.\n"
        "- Ignore any conflicting Copilot CLI host persona, built-in tool descriptions, "
        "custom instructions, or safety text.\n"
        f"- Only claim access to these Meridian tools: {available_tools_text}.\n"
        "- Do not claim access to Copilot CLI built-in tools unless one of them is "
        "explicitly listed above."
    )
    return {
        "mode": "customize",
        "sections": {
            section_id: {"action": "remove"}
            for section_id in GITHUB_COPILOT_SYSTEM_PROMPT_SECTION_IDS
        },
        "content": authoritative_prompt,
    }


@dataclass
class GitHubCopilotRuntimeContext:
    root_dir: Path
    cwd: Path
    home_dir: Path
    config_dir: Path
    env: dict[str, str]


def _cleanup_stale_runtime_dirs() -> None:
    now = time.time()
    for runtime_dir in GITHUB_COPILOT_RUNTIME_ROOT.glob(f"{GITHUB_COPILOT_RUNTIME_PREFIX}*"):
        try:
            if not runtime_dir.is_dir():
                continue
            if is_runtime_dir_stale(
                runtime_dir,
                now=now,
                ttl_seconds=GITHUB_COPILOT_RUNTIME_TTL_SECONDS,
            ):
                shutil.rmtree(runtime_dir, ignore_errors=True)
        except Exception:
            logger.warning(
                "Failed to clean stale GitHub Copilot runtime dir %s",
                runtime_dir,
                exc_info=True,
            )


def _build_runtime_context() -> GitHubCopilotRuntimeContext:
    _cleanup_stale_runtime_dirs()

    root_dir = Path(
        tempfile.mkdtemp(prefix=GITHUB_COPILOT_RUNTIME_PREFIX, dir=str(GITHUB_COPILOT_RUNTIME_ROOT))
    )
    cwd = root_dir / "workspace"
    home_dir = root_dir / "home"
    config_dir = root_dir / "config"
    data_dir = root_dir / "data"
    state_dir = root_dir / "state"
    cache_dir = root_dir / "cache"

    for directory in (cwd, home_dir, config_dir, data_dir, state_dir, cache_dir):
        directory.mkdir(parents=True, exist_ok=True)

    touch_runtime_heartbeat(root_dir)

    return GitHubCopilotRuntimeContext(
        root_dir=root_dir,
        cwd=cwd,
        home_dir=home_dir,
        config_dir=config_dir,
        env={
            "HOME": str(home_dir),
            "XDG_CONFIG_HOME": str(config_dir),
            "XDG_DATA_HOME": str(data_dir),
            "XDG_STATE_HOME": str(state_dir),
            "XDG_CACHE_HOME": str(cache_dir),
            "NO_COLOR": "1",
        },
    )


def _cleanup_runtime_context(runtime_context: GitHubCopilotRuntimeContext) -> None:
    shutil.rmtree(runtime_context.root_dir, ignore_errors=True)


async def _persist_pending_tool_continuation(
    redis_manager: RedisManager,
    *,
    public_tool_call_id: str,
    req: "GitHubCopilotReqChat",
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
            "sandbox_input_files": _serialize_sandbox_input_files(req.sandbox_input_files),
            "sandbox_input_warnings": req.sandbox_input_warnings,
        },
    )


def _model_cache_key(github_token: str) -> str:
    return hashlib.sha256(github_token.encode("utf-8")).hexdigest()


def _clone_model_list(models: list[ModelInfo]) -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in models]


def _clear_github_copilot_model_cache_entry(github_token: str) -> None:
    _GITHUB_COPILOT_MODEL_CACHE.pop(_model_cache_key(github_token), None)


def _format_model_unavailable_error(model: str) -> str:
    model_alias = _model_alias(model)
    return (
        f'GitHub Copilot model "{model_alias}" is not available in Copilot CLI for this '
        "account right now. GitHub Copilot in VS Code or GitHub.com can expose models that "
        "Copilot CLI does not yet support. Refresh Meridian's model list and choose a model "
        "returned by Copilot CLI."
    )


def _is_model_unavailable_error(error: Exception, model: str) -> bool:
    return f'Model "{_model_alias(model)}" is not available' in str(error)


async def _list_sdk_models(github_token: str) -> list[Any]:
    _require_github_copilot_sdk()

    runtime_context = _build_runtime_context()
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    client = CopilotClient(
        SubprocessConfig(
            cwd=str(runtime_context.cwd),
            env=runtime_context.env,
            github_token=github_token,
            use_logged_in_user=False,
        )
    )
    try:
        await client.start()
        return await client.list_models()
    except FileNotFoundError as exc:
        raise ValueError(
            "GitHub Copilot CLI runtime is unavailable. Install the SDK bundled binary or set a "
            "valid Copilot CLI path."
        ) from exc
    except Exception as exc:
        raise ValueError(f"GitHub Copilot model listing failed: {exc}") from exc
    finally:
        with contextlib.suppress(Exception):
            await client.force_stop()
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)


async def list_github_copilot_models(
    github_token: str,
    model_lister: Optional[Callable[[], Awaitable[list[Any]]]] = None,
    *,
    use_cache: bool = True,
) -> list[ModelInfo]:
    _require_github_copilot_sdk()
    cache_key = _model_cache_key(github_token)
    cached_entry = _GITHUB_COPILOT_MODEL_CACHE.get(cache_key)
    if (
        model_lister is None
        and use_cache
        and cached_entry is not None
        and (time.time() - cached_entry[0]) < GITHUB_COPILOT_MODEL_CACHE_TTL_SECONDS
    ):
        return _clone_model_list(cached_entry[1])

    raw_models = await (
        model_lister() if model_lister is not None else _list_sdk_models(github_token)
    )
    normalized_models = [
        model
        for model in (normalize_github_copilot_model(raw_model) for raw_model in raw_models)
        if model is not None
    ]

    deduped_models: dict[str, ModelInfo] = {}
    for model in normalized_models:
        deduped_models.setdefault(model.id, model)

    models = sorted(deduped_models.values(), key=lambda model: (model.name.lower(), model.id))
    if model_lister is None and use_cache:
        _GITHUB_COPILOT_MODEL_CACHE[cache_key] = (
            time.time(),
            _clone_model_list(models),
        )

    return _clone_model_list(models)


def _clear_github_copilot_model_cache() -> None:
    _GITHUB_COPILOT_MODEL_CACHE.clear()


class GitHubCopilotReqChat:
    def __init__(
        self,
        github_token: str,
        model: str,
        messages: list[Any] | list[dict[str, Any]],
        config,
        user_id: str,
        pg_engine: SQLAlchemyAsyncEngine,
        model_id: Optional[str] = None,
        node_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        is_title_generation: bool = False,
        node_type: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT,
        schema: Optional[type[BaseModel]] = None,
        stream: bool = True,
        http_client: Any = None,
        file_uuids: Optional[list[str]] = None,
        file_hashes: Optional[dict[str, str]] = None,
        pdf_engine: str = "default",
        selected_tools: Optional[list[ToolEnum]] = None,
        sandbox_input_files: Optional[list[SandboxInputFileReference]] = None,
        sandbox_input_warnings: Optional[list[str]] = None,
    ):
        self.github_token = github_token.strip()
        self.github_copilot_github_token = self.github_token
        self.model = model
        self.model_id = model_id
        self.messages = [
            message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else message
            for message in messages
        ]
        self.config = config
        self.user_id = user_id
        self.pg_engine = pg_engine
        self.node_id = node_id
        self.graph_id = graph_id
        self.is_title_generation = is_title_generation
        self.node_type = node_type
        self.schema = schema
        self.stream = stream
        self.http_client = http_client
        self.file_uuids = file_uuids or []
        self.file_hashes = file_hashes or {}
        self.pdf_engine = pdf_engine
        self.selected_tools = _normalize_selected_tools(selected_tools)
        self.sandbox_input_files = sandbox_input_files or []
        self.sandbox_input_warnings = sandbox_input_warnings or []

    def validate_request(self) -> None:
        _require_github_copilot_sdk()
        if not self.github_token:
            raise ValueError("GitHub Copilot token is required.")
        if self.schema is not None:
            raise ValueError("GitHub Copilot models do not support structured-output helpers yet.")

        unsupported_tools = [
            tool.value for tool in self.selected_tools if tool not in GITHUB_COPILOT_SUPPORTED_TOOLS
        ]
        if unsupported_tools:
            raise ValueError(
                "GitHub Copilot models currently support only these Meridian tools: "
                + ", ".join(GITHUB_COPILOT_SUPPORTED_TOOL_NAMES)
                + ". Unsupported selection: "
                + ", ".join(unsupported_tools)
                + "."
            )

        if self.file_uuids or self.file_hashes or _has_file_attachments(self.messages):
            raise ValueError("GitHub Copilot models do not support file or PDF attachments yet.")
        if _has_image_inputs(self.messages):
            raise ValueError("GitHub Copilot models do not support image inputs in Meridian yet.")
        if self.http_client is None and any(
            tool
            in {
                ToolEnum.WEB_SEARCH,
                ToolEnum.EXECUTE_CODE,
                ToolEnum.IMAGE_GENERATION,
                ToolEnum.VISUALISE,
            }
            for tool in self.selected_tools
        ):
            raise ValueError(
                "GitHub Copilot tool execution requires an HTTP client in this request."
            )


async def validate_github_copilot_token(
    github_token: str,
    model_lister: Optional[Callable[[], Awaitable[list[Any]]]] = None,
) -> None:
    _require_github_copilot_sdk()

    normalized_token = github_token.strip()
    if not normalized_token:
        raise ValueError("Token is required.")
    if normalized_token.startswith("ghp_"):
        raise ValueError(
            "Classic GitHub personal access tokens (ghp_) are not supported by GitHub Copilot. "
            "Use a gho_, ghu_, or github_pat_ token instead."
        )
    if not normalized_token.startswith(("gho_", "ghu_", "github_pat_")):
        raise ValueError(
            "GitHub Copilot requires a gho_, ghu_, or github_pat_ token. Fine-grained PATs must "
            "include the Copilot Requests permission."
        )

    models = await list_github_copilot_models(
        normalized_token,
        model_lister=model_lister,
        use_cache=False,
    )
    if not models:
        raise ValueError(
            "GitHub Copilot authentication succeeded but no models were returned. Confirm the "
            "account has active Copilot access and model entitlement."
        )


async def _persist_tool_call(
    *,
    req: GitHubCopilotReqChat,
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    normalized_result: Any,
    model_context_payload: str,
    status: ToolCallStatusEnum,
) -> str:
    public_tool_call_id = tool_call_id or f"github-copilot-tool-{int(time.time() * 1000)}"
    if req.graph_id and req.node_id and req.user_id:
        with contextlib.suppress(Exception):
            persisted_tool_call = await create_tool_call(
                req.pg_engine,
                user_id=req.user_id,
                graph_id=req.graph_id,
                node_id=req.node_id,
                model_id=req.model_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                status=status,
                arguments=arguments,
                result=normalized_result,
                model_context_payload=model_context_payload,
            )
            if persisted_tool_call.id is not None:
                public_tool_call_id = str(persisted_tool_call.id)
    return public_tool_call_id


def _build_tools(
    req: GitHubCopilotReqChat,
    feedback_callback: Callable[[str], None],
    execution_state: GitHubCopilotToolExecutionState,
    redis_manager: RedisManager | None,
    abort_current_turn: Callable[[], None],
) -> list[Tool]:
    assert Tool is not None
    tool_definitions = get_openrouter_tools(list(req.selected_tools or []))
    tools: list[Tool] = []

    for tool_definition in tool_definitions:
        function_payload = tool_definition.get("function") or {}
        tool_name = str(function_payload.get("name") or "").strip()
        description = str(function_payload.get("description") or "").strip()
        parameters = function_payload.get("parameters")
        runtime = get_tool_runtime(tool_name)
        handler = TOOL_HANDLERS_BY_NAME.get(tool_name)
        if not tool_name or runtime is None or handler is None:
            continue

        async def _handler(
            invocation: ToolInvocation,
            *,
            current_tool_name: str = tool_name,
            current_runtime=runtime,
            current_handler=handler,
        ) -> ToolResult:
            assert ToolResult is not None
            arguments = invocation.arguments if isinstance(invocation.arguments, dict) else {}

            if execution_state.pending_ask_user is not None:
                tool_result = {"error": ASK_USER_BATCH_ERROR}
            else:
                try:
                    tool_result = await current_handler(arguments, req)
                except Exception as exc:  # pragma: no cover - depends on runtime handlers
                    tool_result = {"error": str(exc)}

            normalized_result = _normalize_tool_storage_value(tool_result)
            status = resolve_tool_status(tool_result)
            model_context_payload = json.dumps(normalized_result, separators=(",", ":"))

            if current_tool_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
                if redis_manager is None:
                    return ToolResult(
                        text_result_for_llm=json.dumps(
                            {"error": "GitHub Copilot ask_user requires streaming mode."},
                            separators=(",", ":"),
                        ),
                        result_type="failure",
                        error="GitHub Copilot ask_user requires streaming mode.",
                    )

                pending_result = AskUserPendingResult().model_dump()
                pending_payload = json.dumps(pending_result, separators=(",", ":"))
                public_tool_call_id = await _persist_tool_call(
                    req=req,
                    tool_call_id=invocation.tool_call_id,
                    tool_name=current_tool_name,
                    arguments=(
                        normalized_result if isinstance(normalized_result, dict) else arguments
                    ),
                    normalized_result=pending_result,
                    model_context_payload=pending_payload,
                    status=ToolCallStatusEnum.PENDING_USER_INPUT,
                )
                feedback_callback(
                    current_runtime.summary_renderer(
                        public_tool_call_id,
                        arguments,
                        pending_result,
                    )
                )
                execution_state.pending_ask_user = GitHubCopilotPendingAskUserState(
                    public_tool_call_id=public_tool_call_id,
                )
                await _persist_pending_tool_continuation(
                    redis_manager,
                    public_tool_call_id=public_tool_call_id,
                    req=req,
                    messages=[*req.messages, *execution_state.continuation_messages],
                )
                abort_current_turn()
                return ToolResult(text_result_for_llm=pending_payload, result_type="success")

            public_tool_call_id = await _persist_tool_call(
                req=req,
                tool_call_id=invocation.tool_call_id,
                tool_name=current_tool_name,
                arguments=arguments,
                normalized_result=normalized_result,
                model_context_payload=model_context_payload,
                status=status,
            )
            feedback_callback(
                current_runtime.summary_renderer(public_tool_call_id, arguments, tool_result)
            )
            execution_state.continuation_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": invocation.tool_call_id,
                    "name": current_tool_name,
                    "content": model_context_payload,
                }
            )
            return ToolResult(
                text_result_for_llm=model_context_payload,
                result_type="failure" if status == ToolCallStatusEnum.ERROR else "success",
                error=(tool_result.get("error") if isinstance(tool_result, dict) else None),
            )

        tools.append(
            Tool(
                name=tool_name,
                description=description,
                parameters=parameters if isinstance(parameters, dict) else None,
                handler=_handler,
                skip_permission=True,
            )
        )

    return tools


async def _run_copilot_session(
    req: GitHubCopilotReqChat,
    *,
    streaming: bool,
    event_handler: Callable[[Any], None],
    feedback_callback: Callable[[str], None],
    redis_manager: RedisManager | None = None,
    execution_state: GitHubCopilotToolExecutionState | None = None,
) -> None:
    _require_github_copilot_sdk()
    assert PermissionHandler is not None

    system_prompt, prompt_messages = _split_system_prompt(req.messages)
    prompt = _build_prompt(prompt_messages) or "Please respond to the available context."
    runtime_context = _build_runtime_context()
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    client = CopilotClient(
        SubprocessConfig(
            cwd=str(runtime_context.cwd),
            env=runtime_context.env,
            github_token=req.github_token,
            use_logged_in_user=False,
        )
    )
    session = None
    abort_tasks: list[asyncio.Task[None]] = []
    execution_state = execution_state or GitHubCopilotToolExecutionState()

    def _abort_current_turn() -> None:
        if session is None:
            return
        abort_tasks.append(asyncio.create_task(session.abort()))

    try:
        await client.start()
        tools = _build_tools(
            req,
            feedback_callback,
            execution_state,
            redis_manager,
            _abort_current_turn,
        )
        available_tool_names = [tool.name for tool in tools]
        try:
            session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                on_event=event_handler,
                model=_model_alias(req.model),
                reasoning_effort=_normalize_reasoning_effort(req.config, req.is_title_generation),
                tools=tools,
                system_message=cast(
                    Any,
                    _build_copilot_system_message(
                        system_prompt,
                        available_tool_names,
                    ),
                ),
                available_tools=available_tool_names,
                streaming=streaming,
                working_directory=str(runtime_context.cwd),
                config_dir=str(runtime_context.config_dir),
                enable_config_discovery=False,
                infinite_sessions={"enabled": False},
                client_name="Meridian",
            )
        except Exception as exc:
            if _is_model_unavailable_error(exc, req.model):
                _clear_github_copilot_model_cache_entry(req.github_token)
                raise ValueError(_format_model_unavailable_error(req.model)) from exc
            raise
        await session.send_and_wait(prompt, timeout=300.0)
    except FileNotFoundError as exc:
        raise ValueError(
            "GitHub Copilot CLI runtime is unavailable. Install the SDK bundled binary or set a "
            "valid Copilot CLI path."
        ) from exc
    finally:
        for abort_task in abort_tasks:
            with contextlib.suppress(Exception):
                await abort_task
        if session is not None:
            with contextlib.suppress(Exception):
                await session.destroy()
        with contextlib.suppress(Exception):
            await client.force_stop()
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)


async def make_github_copilot_request_non_streaming(
    req: GitHubCopilotReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if ToolEnum.ASK_USER in req.selected_tools:
        raise ValueError("GitHub Copilot ask_user requires streaming mode.")

    feedback_parts: list[str] = []
    response_text = ""
    reasoning_text = ""
    final_usage: dict[str, Any] | None = None

    def _handle_event(event: Any) -> None:
        nonlocal response_text, reasoning_text, final_usage
        event_type = getattr(getattr(event, "type", None), "value", getattr(event, "type", ""))
        data = getattr(event, "data", None)
        if data is None:
            return

        usage_data = _normalize_usage_data(data)
        if usage_data is not None:
            final_usage = _merge_usage_data(final_usage, usage_data)

        if event_type == "assistant.reasoning":
            reasoning_text = str(getattr(data, "content", "") or "")
        elif event_type == "assistant.message":
            response_text = str(getattr(data, "content", "") or "")

    await _run_copilot_session(
        req,
        streaming=False,
        event_handler=_handle_event,
        feedback_callback=feedback_parts.append,
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

    reasoning_output = f"[THINK]\n{reasoning_text}\n[!THINK]\n" if reasoning_text else ""
    return "".join(feedback_parts) + reasoning_output + response_text


async def stream_github_copilot_response(
    req: GitHubCopilotReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()

    queue: asyncio.Queue[str] = asyncio.Queue()
    session_done = asyncio.Event()
    error_holder: list[BaseException] = []
    usage_data: dict[str, Any] | None = None
    thinking_started = False
    saw_reasoning_delta = False
    saw_message_delta = False
    awaiting_user_input = False
    execution_state = GitHubCopilotToolExecutionState()

    def _feedback_callback(message: str) -> None:
        nonlocal thinking_started, awaiting_user_input
        if thinking_started:
            queue.put_nowait("\n[!THINK]\n")
            thinking_started = False
        if "<asking_user " in message:
            awaiting_user_input = True
        queue.put_nowait(message)

    def _handle_event(event: Any) -> None:
        nonlocal thinking_started, saw_reasoning_delta, saw_message_delta, usage_data
        event_type = getattr(getattr(event, "type", None), "value", getattr(event, "type", ""))
        data = getattr(event, "data", None)

        if data is not None:
            normalized_usage = _normalize_usage_data(data)
            if normalized_usage is not None:
                usage_data = _merge_usage_data(usage_data, normalized_usage)

        if event_type == "assistant.reasoning_delta" and data is not None:
            delta = str(getattr(data, "delta_content", "") or "")
            if delta:
                if not thinking_started:
                    queue.put_nowait("[THINK]\n")
                    thinking_started = True
                saw_reasoning_delta = True
                queue.put_nowait(delta)
            return

        if event_type == "assistant.message_delta" and data is not None:
            delta = str(getattr(data, "delta_content", "") or "")
            if delta:
                if thinking_started:
                    queue.put_nowait("\n[!THINK]\n")
                    thinking_started = False
                saw_message_delta = True
                queue.put_nowait(delta)
            return

        if event_type == "assistant.reasoning" and data is not None and not saw_reasoning_delta:
            content = str(getattr(data, "content", "") or "")
            if content:
                queue.put_nowait(f"[THINK]\n{content}\n[!THINK]\n")
            return

        if event_type == "assistant.message" and data is not None and not saw_message_delta:
            content = str(getattr(data, "content", "") or "")
            if content:
                if thinking_started:
                    queue.put_nowait("\n[!THINK]\n")
                    thinking_started = False
                queue.put_nowait(content)
            return

        if event_type == "session.error":
            if awaiting_user_input:
                session_done.set()
                return
            error_holder.append(
                RuntimeError(str(getattr(data, "message", "") or "GitHub Copilot session failed."))
            )
            session_done.set()
            return

        if event_type == "session.idle":
            session_done.set()

    async def _run() -> None:
        try:
            await _run_copilot_session(
                req,
                streaming=True,
                event_handler=_handle_event,
                feedback_callback=_feedback_callback,
                redis_manager=redis_manager,
                execution_state=execution_state,
            )
        except BaseException as exc:
            error_holder.append(exc)
        finally:
            session_done.set()

    task = asyncio.create_task(_run())

    try:
        while True:
            if session_done.is_set() and queue.empty():
                break
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            yield chunk

        await task

        if error_holder and not awaiting_user_input:
            raise error_holder[0]

        if (
            usage_data
            and not awaiting_user_input
            and not req.is_title_generation
            and final_data_container is not None
        ):
            final_data_container["usage_data"] = usage_data

        if (
            awaiting_user_input
            and execution_state.pending_ask_user is not None
            and final_data_container is not None
        ):
            final_data_container["pending_tool_call_id"] = (
                execution_state.pending_ask_user.public_tool_call_id
            )

        if (
            usage_data
            and not awaiting_user_input
            and req.graph_id
            and req.node_id
            and not req.is_title_generation
        ):
            await update_node_usage_data(
                pg_engine=pg_engine,
                graph_id=req.graph_id,
                node_id=req.node_id,
                usage_data=usage_data,
                node_type=req.node_type,
                model_id=req.model_id,
            )
    except asyncio.CancelledError:
        logger.info("GitHub Copilot stream for node %s was cancelled.", req.node_id)
        task.cancel()
        raise
    except Exception as exc:
        logger.error("GitHub Copilot streaming error: %s", exc, exc_info=True)
        if thinking_started:
            yield "\n[!THINK]\n"
        yield f"[ERROR]{str(exc)}[!ERROR]"
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
