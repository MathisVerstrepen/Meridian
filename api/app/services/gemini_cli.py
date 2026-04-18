import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.token_ops.provider_token_crud import store_provider_token_if_current_matches
from database.redis.redis_ops import RedisManager
from models.message import MessageContentTypeEnum, NodeTypeEnum, ToolEnum
from pydantic import BaseModel
from services.crypto import encrypt_api_key
from services.openrouter import _process_tool_calls_and_continue
from services.provider_runtime import (
    is_runtime_dir_stale,
    start_runtime_heartbeat,
    stop_runtime_heartbeat,
    touch_runtime_heartbeat,
)
from services.providers.gemini_cli_bridge_utils import extract_bridge_json_payload
from services.providers.gemini_cli_catalog import GEMINI_CLI_MODEL_PREFIX, GEMINI_CLI_PROVIDER_KEY
from services.sandbox_inputs import SandboxInputFileReference
from services.tools import get_openrouter_tools
from services.usage_data import (
    append_usage_request_breakdown,
    build_usage_request_breakdown,
    extract_tool_names,
    finalize_usage_data,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

GEMINI_CLI_RUNTIME_PREFIX = "meridian-gemini-cli-"
GEMINI_CLI_RUNTIME_ROOT = Path("/tmp")
GEMINI_CLI_RUNTIME_TTL_SECONDS = 60 * 60
GEMINI_CLI_BRIDGE_TIMEOUT_SECONDS = 180.0
GEMINI_CLI_BRIDGE_STREAM_TIMEOUT_SECONDS = 300.0
GEMINI_CLI_SUPPORTED_TOOLS = {
    ToolEnum.WEB_SEARCH,
    ToolEnum.LINK_EXTRACTION,
    ToolEnum.EXECUTE_CODE,
    ToolEnum.IMAGE_GENERATION,
    ToolEnum.VISUALISE,
    ToolEnum.ASK_USER,
}


@dataclass
class GeminiCliRuntimeContext:
    root_dir: Path
    cwd: Path
    env: dict[str, str]
    oauth_creds_path: Path


def _resolve_bridge_script() -> Path:
    return Path(__file__).resolve().parents[1] / "gemini_cli_runtime" / "bridge.mjs"


def _normalize_oauth_creds_json(raw_value: str) -> str:
    payload = _parse_oauth_creds_json(raw_value)

    missing_keys: list[str] = []
    if not str(payload.get("access_token") or "").strip():
        missing_keys.append("access_token")
    if not str(payload.get("refresh_token") or "").strip():
        missing_keys.append("refresh_token")
    if "expiry_date" not in payload or payload.get("expiry_date") in (None, ""):
        missing_keys.append("expiry_date")

    if missing_keys:
        raise ValueError(
            "Gemini CLI OAuth credentials are missing required keys: "
            + ", ".join(sorted(missing_keys))
        )

    return _serialize_oauth_creds_payload(payload)


def _parse_oauth_creds_json(raw_value: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini CLI OAuth credentials must be valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Gemini CLI OAuth credentials must be a JSON object.")

    return payload


def _serialize_oauth_creds_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _merge_refreshed_oauth_creds_json(current_value: str, updated_value: str) -> str:
    current_payload = _parse_oauth_creds_json(current_value)
    updated_payload = _parse_oauth_creds_json(updated_value)
    merged_payload = dict(current_payload)

    for key, value in updated_payload.items():
        if key == "refresh_token":
            if str(value or "").strip():
                merged_payload[key] = value
            continue
        if key == "expiry_date":
            if value not in (None, "", 0):
                merged_payload[key] = value
            continue
        if key == "access_token":
            if str(value or "").strip():
                merged_payload[key] = value
            continue
        if value is not None:
            merged_payload[key] = value

    return _serialize_oauth_creds_payload(merged_payload)


def _model_alias(model_id: str) -> str:
    if model_id.startswith(GEMINI_CLI_MODEL_PREFIX):
        return model_id[len(GEMINI_CLI_MODEL_PREFIX) :]
    return model_id


def _has_pdf_attachments(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != MessageContentTypeEnum.file.value:
                continue
            file_payload = item.get("file")
            if isinstance(file_payload, dict) and file_payload.get("file_data"):
                return True
    return False


def _has_image_inputs(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == MessageContentTypeEnum.image_url.value:
                return True
    return False


def _summarize_messages_for_log(messages: list[dict[str, Any]]) -> list[str]:
    summary: list[str] = []
    for message in messages[:8]:
        role = str(message.get("role") or "user")
        content = message.get("content")
        if isinstance(content, str):
            summary.append(f"{role}:text")
            continue
        if not isinstance(content, list):
            summary.append(f"{role}:empty")
            continue

        part_types: list[str] = []
        for item in content[:6]:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "unknown")
            if item_type == MessageContentTypeEnum.file.value:
                file_payload = item.get("file")
                content_type = (
                    str(file_payload.get("content_type") or "").strip()
                    if isinstance(file_payload, dict)
                    else ""
                )
                part_types.append(f"file:{content_type}" if content_type else "file")
            else:
                part_types.append(item_type)

        summary.append(f"{role}:{'+'.join(part_types) if part_types else 'empty'}")

    return summary


def _cleanup_stale_runtime_dirs() -> None:
    now = time.time()
    for runtime_dir in GEMINI_CLI_RUNTIME_ROOT.glob(f"{GEMINI_CLI_RUNTIME_PREFIX}*"):
        try:
            if not runtime_dir.is_dir():
                continue
            if is_runtime_dir_stale(
                runtime_dir,
                now=now,
                ttl_seconds=GEMINI_CLI_RUNTIME_TTL_SECONDS,
            ):
                shutil.rmtree(runtime_dir, ignore_errors=True)
        except Exception:
            logger.warning(
                "Failed to clean stale Gemini CLI runtime dir %s",
                runtime_dir,
                exc_info=True,
            )


def _build_runtime_context(oauth_creds_json: str) -> GeminiCliRuntimeContext:
    _cleanup_stale_runtime_dirs()

    root_dir = Path(
        tempfile.mkdtemp(prefix=GEMINI_CLI_RUNTIME_PREFIX, dir=str(GEMINI_CLI_RUNTIME_ROOT))
    )
    cwd = root_dir / "workspace"
    home_dir = root_dir / "home"
    config_dir = root_dir / "config"
    data_dir = root_dir / "data"
    state_dir = root_dir / "state"
    cache_dir = root_dir / "cache"
    gemini_dir = home_dir / ".gemini"
    oauth_creds_path = gemini_dir / "oauth_creds.json"

    for directory in (
        cwd,
        home_dir,
        config_dir,
        data_dir,
        state_dir,
        cache_dir,
        gemini_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    touch_runtime_heartbeat(root_dir)

    oauth_creds_path.write_text(oauth_creds_json, encoding="utf-8")

    return GeminiCliRuntimeContext(
        root_dir=root_dir,
        cwd=cwd,
        env={
            "HOME": str(home_dir),
            "XDG_CONFIG_HOME": str(config_dir),
            "XDG_DATA_HOME": str(data_dir),
            "XDG_STATE_HOME": str(state_dir),
            "XDG_CACHE_HOME": str(cache_dir),
            "NO_COLOR": "1",
        },
        oauth_creds_path=oauth_creds_path,
    )


def _build_subprocess_env(runtime_context: GeminiCliRuntimeContext) -> dict[str, str]:
    passthrough_env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key == "PATH" or key == "LANG" or key.startswith("LC_"):
            passthrough_env[key] = value
    return {**passthrough_env, **runtime_context.env}


def _cleanup_runtime_context(runtime_context: GeminiCliRuntimeContext) -> None:
    try:
        shutil.rmtree(runtime_context.root_dir, ignore_errors=True)
    except Exception:
        logger.warning(
            "Failed to cleanup Gemini CLI runtime dir %s",
            runtime_context.root_dir,
            exc_info=True,
        )


def _normalize_max_tokens(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return min(parsed, 65536)


def _bridge_payload(
    *,
    req: Optional["GeminiCliReqChat"] = None,
    model: str,
    messages: list[dict[str, Any]],
    schema: Optional[type[BaseModel]] = None,
) -> dict[str, Any]:
    config = getattr(req, "config", None)
    settings = {
        "temperature": getattr(config, "temperature", None),
        "top_p": getattr(config, "top_p", None),
        "top_k": getattr(config, "top_k", None),
        "max_tokens": _normalize_max_tokens(getattr(config, "max_tokens", None)),
        "reasoning_effort": getattr(config, "reasoning_effort", None),
        "exclude_reasoning": bool(getattr(config, "exclude_reasoning", False)),
        "is_title_generation": bool(getattr(req, "is_title_generation", False)),
    }
    tools = get_openrouter_tools(list(getattr(req, "selected_tools", []) or []))
    return {
        "model": _model_alias(model),
        "messages": messages,
        "settings": settings,
        "schema": schema.model_json_schema() if schema is not None else None,
        "tools": tools,
    }


def _bridge_error_detail(payload: dict[str, Any] | None, stderr_text: str) -> str:
    if isinstance(payload, dict) and payload.get("error"):
        return _format_bridge_error_value(payload["error"])
    if stderr_text:
        return stderr_text
    return "Gemini CLI bridge failed."


def _iter_bridge_error_dicts(error_value: Any) -> list[dict[str, Any]]:
    if isinstance(error_value, dict):
        candidate = error_value.get("error")
        if isinstance(candidate, dict):
            nested = candidate.get("error")
            if isinstance(nested, dict):
                return [nested]
            return [candidate]
        return [error_value]

    if isinstance(error_value, list):
        collected: list[dict[str, Any]] = []
        for item in error_value:
            collected.extend(_iter_bridge_error_dicts(item))
        return collected

    return []


def _extract_bridge_retry_delay(message: str) -> str | None:
    match = re.search(r"reset after\s+([^\.]+)", message, flags=re.IGNORECASE)
    if not match:
        return None
    delay = match.group(1).strip()
    return delay.rstrip(".") or None


def _format_bridge_rate_limit_error(
    error_payload: dict[str, Any], request_summary: dict[str, Any] | None
) -> str | None:
    status_text = str(error_payload.get("status") or "").strip().upper()
    code_value = error_payload.get("code")
    raw_message = str(error_payload.get("message") or "").strip()

    reasons: set[str] = set()
    errors = error_payload.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                reason = str(item.get("reason") or "").strip().upper()
                if reason:
                    reasons.add(reason)

    details = error_payload.get("details")
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason") or "").strip().upper()
            if reason:
                reasons.add(reason)

    is_rate_limited = (
        code_value == 429
        or status_text == "RESOURCE_EXHAUSTED"
        or "RATELIMITEXCEEDED" in reasons
        or "RATE_LIMIT_EXCEEDED" in reasons
    )
    if not is_rate_limited:
        return None

    model_name = ""
    if isinstance(request_summary, dict):
        model_name = str(
            request_summary.get("resolved_model") or request_summary.get("requested_model") or ""
        ).strip()

    if not model_name and isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                model_name = str(metadata.get("model") or "").strip()
                if model_name:
                    break

    retry_delay = _extract_bridge_retry_delay(raw_message)
    message = "Gemini CLI quota exhausted for this model"
    if model_name:
        message += f" ({model_name})"
    if retry_delay:
        message += f". Retry in about {retry_delay}."
    else:
        message += ". Retry shortly."
    return message


def _format_bridge_error_value(error_value: Any) -> str:
    if isinstance(error_value, str):
        return error_value

    if not isinstance(error_value, dict):
        return str(error_value)

    request_summary = error_value.get("request_summary")
    inner_error = error_value.get("error")
    message = error_value.get("message")

    error_payloads = _iter_bridge_error_dicts(inner_error)
    if error_payloads:
        rate_limit_detail = _format_bridge_rate_limit_error(error_payloads[0], request_summary)
        if rate_limit_detail:
            return rate_limit_detail

        error_payload = error_payloads[0]
        pieces = [
            str(error_payload.get("message") or "Gemini CLI request failed."),
        ]
        status_text = str(error_payload.get("status") or "").strip()
        if status_text:
            pieces.append(f"status={status_text}")
        code_value = error_payload.get("code")
        if code_value is not None:
            pieces.append(f"code={code_value}")
        detail = ", ".join(pieces)
    elif isinstance(message, str) and message.strip():
        detail = message.strip()
    else:
        detail = str(error_value)

    if not isinstance(request_summary, dict):
        return detail

    summary_bits: list[str] = []
    requested_model = str(request_summary.get("requested_model") or "").strip()
    resolved_model = str(request_summary.get("resolved_model") or "").strip()
    if requested_model or resolved_model:
        summary_bits.append(f"model={requested_model or '?'}->{resolved_model or '?'}")

    tool_names = request_summary.get("tool_names")
    if isinstance(tool_names, list) and tool_names:
        summary_bits.append("tools=" + ",".join(str(tool_name) for tool_name in tool_names))

    generation_config_keys = request_summary.get("generation_config_keys")
    if isinstance(generation_config_keys, list) and generation_config_keys:
        summary_bits.append("config_keys=" + ",".join(str(key) for key in generation_config_keys))

    message_summary = request_summary.get("message_summary")
    if isinstance(message_summary, list) and message_summary:
        compact_messages = []
        for item in message_summary[:6]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "?")
            part_types = item.get("part_types")
            part_text = (
                "+".join(str(part_type) for part_type in part_types)
                if isinstance(part_types, list) and part_types
                else "empty"
            )
            tool_call_count = item.get("tool_call_count")
            tool_suffix = f"/tool_calls={tool_call_count}" if tool_call_count else ""
            compact_messages.append(f"{role}:{part_text}{tool_suffix}")
        if compact_messages:
            summary_bits.append("messages=" + ";".join(compact_messages))

    if not summary_bits:
        return detail

    return f"{detail} ({'; '.join(summary_bits)})"


async def _run_bridge_json(
    *,
    command: str,
    payload: dict[str, Any],
    runtime_context: GeminiCliRuntimeContext,
    timeout_seconds: float = GEMINI_CLI_BRIDGE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    bridge_script = _resolve_bridge_script()
    if not bridge_script.is_file():
        raise ValueError("Gemini CLI bridge runtime is unavailable: bridge script was not found.")

    try:
        process = await asyncio.create_subprocess_exec(
            "node",
            str(bridge_script),
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(runtime_context.cwd),
            env=_build_subprocess_env(runtime_context),
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "Gemini CLI bridge runtime is unavailable: 'node' is not installed."
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=json.dumps(payload).encode("utf-8")),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise ValueError("Gemini CLI bridge timed out.") from exc

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()

    response_payload = extract_bridge_json_payload(stdout_text)

    if process.returncode != 0:
        logger.error(
            "Gemini CLI bridge failed: returncode=%s payload=%s stderr=%s",
            process.returncode,
            response_payload,
            stderr_text,
        )
        detail = _bridge_error_detail(response_payload, stderr_text)
        if detail == "Gemini CLI bridge failed." and stdout_text:
            detail = stdout_text
        raise ValueError(detail)

    if response_payload is None:
        if stdout_text:
            raise ValueError(stdout_text)
        raise RuntimeError("Gemini CLI bridge returned no response payload.")

    if response_payload.get("ok") is False:
        logger.error(
            "Gemini CLI bridge returned application error: payload=%s stderr=%s",
            response_payload,
            stderr_text,
        )
        raise ValueError(_bridge_error_detail(response_payload, stderr_text))

    return response_payload


async def _persist_refreshed_oauth_creds(
    req: "GeminiCliReqChat",
    updated_oauth_creds_json: str | None,
) -> None:
    if not updated_oauth_creds_json:
        return

    normalized = _merge_refreshed_oauth_creds_json(req.oauth_creds_json, updated_oauth_creds_json)
    if normalized == req.oauth_creds_json:
        return

    encrypted_oauth_creds = await encrypt_api_key(normalized)
    if not encrypted_oauth_creds:
        logger.warning("Failed to encrypt refreshed Gemini CLI OAuth credentials.")
        return

    stored = await store_provider_token_if_current_matches(
        req.pg_engine,
        req.user_id,
        GEMINI_CLI_PROVIDER_KEY,
        req.oauth_creds_json,
        encrypted_oauth_creds,
    )
    if not stored:
        logger.info(
            "Skipped storing refreshed Gemini CLI credentials for user %s "
            "due to concurrent update.",
            req.user_id,
        )
    req.oauth_creds_json = normalized


class GeminiCliReqChat:
    def __init__(
        self,
        oauth_creds_json: str,
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
        self.oauth_creds_json = _normalize_oauth_creds_json(oauth_creds_json)
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
        self.selected_tools = selected_tools or []
        self.sandbox_input_files = sandbox_input_files or []
        self.sandbox_input_warnings = sandbox_input_warnings or []

    def validate_request(self) -> None:
        unsupported_tools = [
            tool.value for tool in self.selected_tools if tool not in GEMINI_CLI_SUPPORTED_TOOLS
        ]
        if unsupported_tools:
            unsupported = ", ".join(unsupported_tools)
            raise ValueError(
                "Gemini CLI models currently support only these Meridian tools: "
                "web_search, link_extraction, execute_code, image_generation, visualise, ask_user. "
                f"Unsupported selection: {unsupported}."
            )

        if self.http_client is None and any(
            tool
            in {
                ToolEnum.WEB_SEARCH,
                ToolEnum.LINK_EXTRACTION,
                ToolEnum.EXECUTE_CODE,
                ToolEnum.IMAGE_GENERATION,
                ToolEnum.VISUALISE,
            }
            for tool in self.selected_tools
        ):
            raise ValueError("Gemini CLI tool execution requires an HTTP client in this request.")

        if self.file_uuids and not _has_pdf_attachments(self.messages):
            raise ValueError("Gemini CLI PDF inputs require attachment content in the request.")

    def get_bridge_payload(self) -> dict[str, Any]:
        payload = _bridge_payload(
            req=self,
            model=self.model,
            messages=self.messages,
            schema=self.schema,
        )
        logger.info(
            (
                "Gemini CLI payload: requested_model=%s alias=%s "
                "title_generation=%s tools=%s schema=%s pdf=%s image=%s messages=%s"
            ),
            self.model,
            payload.get("model"),
            self.is_title_generation,
            [tool.value for tool in self.selected_tools],
            self.schema is not None,
            _has_pdf_attachments(self.messages),
            _has_image_inputs(self.messages),
            _summarize_messages_for_log(self.messages),
        )
        return payload


async def validate_gemini_cli_oauth_creds_json(oauth_creds_json: str) -> str:
    normalized_oauth_creds_json = _normalize_oauth_creds_json(oauth_creds_json)
    runtime_context = _build_runtime_context(normalized_oauth_creds_json)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    try:
        payload = await _run_bridge_json(
            command="validate",
            payload={},
            runtime_context=runtime_context,
        )
        updated_oauth_creds_json = str(
            payload.get("oauth_creds_json") or normalized_oauth_creds_json
        )
        return _normalize_oauth_creds_json(updated_oauth_creds_json)
    finally:
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)


async def _request_once_non_streaming(
    req: GeminiCliReqChat,
    runtime_context: GeminiCliRuntimeContext,
) -> dict[str, Any]:
    response_payload = await _run_bridge_json(
        command="generate",
        payload=req.get_bridge_payload(),
        runtime_context=runtime_context,
    )
    await _persist_refreshed_oauth_creds(
        req,
        str(response_payload.get("oauth_creds_json") or "") or None,
    )
    return response_payload


async def make_gemini_cli_request_non_streaming(
    req: GeminiCliReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if ToolEnum.ASK_USER in req.selected_tools:
        raise ValueError("Gemini CLI ask_user requires streaming mode.")

    runtime_context = _build_runtime_context(req.oauth_creds_json)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    try:
        feedback_buffer: list[str] = []
        max_rounds = 5 if req.selected_tools else 1
        response_payload: dict[str, Any] = {}
        final_response_text = ""
        for _ in range(max_rounds):
            response_payload = await _request_once_non_streaming(req, runtime_context)
            tool_calls = response_payload.get("tool_calls")
            clean_text = str(response_payload.get("text") or "")
            thinking_text = str(response_payload.get("thinking") or "")
            final_response_text = (
                ("[THINK]\n" + thinking_text + "\n[!THINK]\n") if thinking_text else ""
            ) + clean_text
            if not tool_calls:
                break

            (
                should_continue,
                _,
                req,
                _,
                feedback_strings,
                awaiting_user_input,
                _,
            ) = await _process_tool_calls_and_continue(
                tool_calls,
                req.messages,
                req,
                None,  # type: ignore[arg-type]
                assistant_content=clean_text or None,
            )
            feedback_buffer.extend(feedback_strings)

            if awaiting_user_input:
                raise ValueError("Gemini CLI ask_user requires streaming mode.")
            if not should_continue:
                break

        usage_data = response_payload.get("usage")
        if (
            isinstance(usage_data, dict)
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

        return "".join(feedback_buffer) + final_response_text
    finally:
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)


async def stream_gemini_cli_response(
    req: GeminiCliReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()
    runtime_context = _build_runtime_context(req.oauth_creds_json)
    heartbeat_task = start_runtime_heartbeat(runtime_context.root_dir)
    usage_data: dict[str, Any] | None = None
    thinking_started = False
    process: asyncio.subprocess.Process | None = None
    request_index = 0

    try:
        while True:
            bridge_script = _resolve_bridge_script()
            if not bridge_script.is_file():
                raise ValueError(
                    "Gemini CLI bridge runtime is unavailable: bridge script was not found."
                )

            try:
                process = await asyncio.create_subprocess_exec(
                    "node",
                    str(bridge_script),
                    "stream",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(runtime_context.cwd),
                    env=_build_subprocess_env(runtime_context),
                )
            except FileNotFoundError as exc:
                raise ValueError(
                    "Gemini CLI bridge runtime is unavailable: 'node' is not installed."
                ) from exc

            payload_bytes = json.dumps(req.get_bridge_payload()).encode("utf-8")
            assert process.stdin is not None
            process.stdin.write(payload_bytes)
            await process.stdin.drain()
            process.stdin.close()

            assistant_content = ""
            tool_calls: list[dict[str, Any]] = []
            round_usage: dict[str, Any] | None = None
            finish_event: dict[str, Any] | None = None

            try:
                assert process.stdout is not None
                while True:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=GEMINI_CLI_BRIDGE_STREAM_TIMEOUT_SECONDS,
                    )
                    if not line:
                        break

                    try:
                        event = json.loads(line.decode("utf-8", errors="replace").strip())
                    except json.JSONDecodeError:
                        continue

                    event_type = str(event.get("type") or "")
                    if event_type == "thinking-delta":
                        delta = str(event.get("delta") or "")
                        if delta:
                            if not thinking_started:
                                yield "[THINK]\n"
                                thinking_started = True
                            yield delta
                        continue

                    if event_type == "text-delta":
                        delta = str(event.get("delta") or "")
                        if delta:
                            if thinking_started:
                                yield "\n[!THINK]\n"
                                thinking_started = False
                            assistant_content += delta
                            yield delta
                        continue

                    if event_type == "tool-call":
                        tool_call = event.get("tool_call")
                        if isinstance(tool_call, dict):
                            tool_calls.append(tool_call)
                        continue

                    if event_type == "debug":
                        continue

                    if event_type == "finish":
                        if thinking_started:
                            yield "\n[!THINK]\n"
                            thinking_started = False
                        finish_event = event
                        break

                    if event_type == "error":
                        if thinking_started:
                            yield "\n[!THINK]\n"
                            thinking_started = False
                        logger.error(
                            "Gemini CLI stream event error: payload=%s request_summary=%s",
                            event.get("error"),
                            event.get("request_summary"),
                        )
                        raise ValueError(
                            _format_bridge_error_value(
                                event.get("error") or "Gemini CLI bridge failed."
                            )
                        )

                stderr_bytes = await process.stderr.read() if process.stderr is not None else b""
                await process.wait()
                stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

                if process.returncode != 0:
                    raise ValueError(stderr_text or "Gemini CLI bridge failed.")
                if finish_event is None:
                    raise RuntimeError("Gemini CLI bridge stream ended without a finish event.")
                process = None
            except asyncio.CancelledError:
                if process is not None:
                    process.kill()
                    await process.communicate()
                process = None
                raise
            except asyncio.TimeoutError as exc:
                if process is not None:
                    process.kill()
                    await process.communicate()
                process = None
                raise ValueError("Gemini CLI bridge timed out.") from exc

            await _persist_refreshed_oauth_creds(
                req,
                str(finish_event.get("oauth_creds_json") or "") or None,
            )
            if isinstance(finish_event.get("usage"), dict):
                round_usage = finish_event.get("usage")

            if round_usage and not req.is_title_generation:
                request_index += 1
                usage_data = append_usage_request_breakdown(
                    usage_data,
                    build_usage_request_breakdown(
                        usage_data=round_usage,
                        index=request_index,
                        model=req.model,
                        finish_reason=str(finish_event.get("finish_reason") or "") or None,
                        tool_names=extract_tool_names(tool_calls),
                    ),
                )

            if tool_calls:
                (
                    should_continue,
                    _,
                    req,
                    _,
                    feedback_strings,
                    awaiting_user_input,
                    pending_tool_call_id,
                ) = await _process_tool_calls_and_continue(
                    tool_calls,
                    req.messages,
                    req,
                    redis_manager,
                    assistant_content=assistant_content or None,
                )
                for feedback in feedback_strings:
                    yield feedback
                if pending_tool_call_id and final_data_container is not None:
                    final_data_container["pending_tool_call_id"] = pending_tool_call_id
                if awaiting_user_input:
                    break
                if should_continue:
                    continue
            break

        usage_data = finalize_usage_data(usage_data)

        if usage_data and not req.is_title_generation and final_data_container is not None:
            final_data_container["usage_data"] = usage_data

        if usage_data and req.graph_id and req.node_id and not req.is_title_generation:
            await update_node_usage_data(
                pg_engine=pg_engine,
                graph_id=req.graph_id,
                node_id=req.node_id,
                usage_data=usage_data,
                node_type=req.node_type,
                model_id=req.model_id,
            )
    except asyncio.CancelledError:
        logger.info("Gemini CLI stream for node %s was cancelled.", req.node_id)
        raise
    except Exception as exc:
        logger.error("Gemini CLI streaming error: %s", exc, exc_info=True)
        if thinking_started:
            yield "\n[!THINK]\n"
        yield f"[ERROR]{str(exc)}[!ERROR]"
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            with contextlib.suppress(Exception):
                await process.communicate()
        await stop_runtime_heartbeat(heartbeat_task)
        _cleanup_runtime_context(runtime_context)
