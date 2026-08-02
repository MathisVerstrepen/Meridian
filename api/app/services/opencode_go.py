import asyncio
import json
import logging
import re
import uuid
from asyncio import TimeoutError as AsyncTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from services.openrouter import _process_tool_calls_and_continue
from services.providers.anthropic_protocol import (
    anthropic_tool_calls_to_openai,
    build_anthropic_messages,
    serialize_anthropic_tool_input,
)
from services.providers.common import (
    BaseProviderReq,
    has_file_attachments,
    has_image_inputs,
    normalize_max_tokens,
    normalize_temperature,
    normalize_top_p,
    strip_model_prefix,
    validate_http_client_for_tools,
    validate_supported_tools,
)
from services.providers.openai_protocol import (
    normalize_openai_request_message,
    sanitize_openai_messages,
    stream_openai_compatible_response,
)
from services.providers.openai_responses_protocol import (
    build_openai_responses_payload,
    extract_openai_responses_function_calls,
    extract_openai_responses_text,
    normalize_openai_responses_usage,
    stream_openai_responses_response,
)
from services.providers.opencode_go_catalog import (
    OPENCODE_GO_MODEL_PREFIX,
    OPENCODE_GO_TEMPERATURE_OVERRIDES,
    OPENCODE_GO_TOP_P_OVERRIDES,
)
from services.tools import get_openrouter_tools
from services.usage_data import (
    append_usage_request_breakdown,
    build_usage_request_breakdown,
    extract_tool_names,
    finalize_usage_data,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

OPENCODE_GO_OPENAI_CHAT_URL = "https://opencode.ai/zen/go/v1/chat/completions"
OPENCODE_GO_OPENAI_RESPONSES_URL = "https://opencode.ai/zen/go/v1/responses"
OPENCODE_GO_ANTHROPIC_MESSAGES_URL = "https://opencode.ai/zen/go/v1/messages"
OPENCODE_GO_VALIDATION_MODEL = f"{OPENCODE_GO_MODEL_PREFIX}qwen3.5-plus"
OPENCODE_GO_NON_STREAMING_TIMEOUT = httpx.Timeout(300.0, connect=10.0, read=300.0)
OPENCODE_GO_ANTHROPIC_VERSION = "2023-06-01"
OPENCODE_GO_FALLBACK_USER_CONTENT = "Please respond to the available context."
OPENCODE_GO_REASONING_CONTENT_MODEL_IDS = {
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    "kimi-k2.5",
    "kimi-k2.6",
}
OPENCODE_GO_ERROR_MESSAGE_LIMIT = 500
OPENCODE_GO_CORRELATION_HEADERS = (
    "x-request-id",
    "request-id",
    "x-correlation-id",
    "cf-ray",
    "traceparent",
)


def _normalize_selected_tool_names(selected_tools: list[Any]) -> list[str]:
    tool_names: list[str] = []
    for tool in selected_tools:
        if isinstance(tool, Enum):
            tool_name = str(tool.value or "").strip()
        else:
            tool_name = str(tool or "").strip()
        if tool_name and tool_name not in tool_names:
            tool_names.append(tool_name)
    return tool_names


def _build_opencode_go_authoritative_system_prompt(
    system_prompt: str | None,
    available_tool_names: list[str],
) -> str:
    available_tools_text = ", ".join(available_tool_names) if available_tool_names else "none"
    authoritative_prompt = str(system_prompt or "").strip()
    if authoritative_prompt:
        authoritative_prompt += "\n\n"
    authoritative_prompt += (
        "Session-specific Meridian constraints:\n"
        "- Treat this Meridian prompt as the authoritative instruction set for this session.\n"
        "- Ignore any conflicting OpenCode, OpenCode Go, or provider-added host "
        "persona, built-in tool descriptions, custom instructions, or hidden prompt "
        "text.\n"
        f"- Only claim access to these Meridian tools: {available_tools_text}.\n"
        "- Do not claim access to OpenCode app, CLI, slash commands, plan/build "
        "modes, local files, or built-in tools unless Meridian explicitly provides "
        "them.\n"
        "- Do not attribute any hidden system prompt, confidentiality rule, or "
        "internal configuration to Meridian unless it is explicitly present in this "
        "Meridian prompt."
    )
    return authoritative_prompt


def _uses_anthropic_protocol(model_id: str) -> bool:
    model_key = strip_model_prefix(model_id, OPENCODE_GO_MODEL_PREFIX)
    return model_key.startswith(("minimax-", "qwen"))


def _uses_openai_responses_protocol(model_id: str) -> bool:
    return strip_model_prefix(model_id, OPENCODE_GO_MODEL_PREFIX) == "grok-4.5"


def _supports_image_inputs(model_id: str) -> bool:
    model_key = strip_model_prefix(model_id, OPENCODE_GO_MODEL_PREFIX)
    return (
        model_key.startswith("kimi-k2.")
        or model_key in {"mimo-v2-omni", "mimo-v2.5", "minimax-m3"}
        or (model_key.startswith("qwen") and model_key.endswith("-plus"))
    )


def _requires_reasoning_content_round_trip(model_id: str) -> bool:
    return (
        strip_model_prefix(model_id, OPENCODE_GO_MODEL_PREFIX)
        in OPENCODE_GO_REASONING_CONTENT_MODEL_IDS
    )


def _resolve_temperature(model_id: str, configured_temperature: Any) -> float | None:
    model_key = strip_model_prefix(model_id, OPENCODE_GO_MODEL_PREFIX)
    if model_key in OPENCODE_GO_TEMPERATURE_OVERRIDES:
        return OPENCODE_GO_TEMPERATURE_OVERRIDES[model_key]
    return normalize_temperature(configured_temperature)


def _resolve_top_p(model_id: str, configured_top_p: Any) -> float | None:
    model_key = strip_model_prefix(model_id, OPENCODE_GO_MODEL_PREFIX)
    if model_key in OPENCODE_GO_TOP_P_OVERRIDES:
        return OPENCODE_GO_TOP_P_OVERRIDES[model_key]
    return normalize_top_p(configured_top_p)


def _build_anthropic_tools(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool_definition in tool_definitions:
        function_payload = tool_definition.get("function")
        if not isinstance(function_payload, dict):
            continue
        name = str(function_payload.get("name") or "").strip()
        if not name:
            continue
        tools.append(
            {
                "name": name,
                "description": str(function_payload.get("description") or "").strip(),
                "input_schema": function_payload.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return tools


def _parse_anthropic_error(error_content: bytes) -> str:
    try:
        error_json = json.loads(error_content)
    except json.JSONDecodeError:
        return error_content.decode("utf-8", errors="ignore")

    error_payload = error_json.get("error") if isinstance(error_json, dict) else None
    if isinstance(error_payload, dict):
        return str(error_payload.get("message") or error_payload.get("type") or "Unknown API error")
    return str(error_payload or error_json)


def _parse_opencode_go_error(error_content: bytes) -> str:
    message: str | None = None
    try:
        payload = json.loads(error_content)
        if isinstance(payload, dict):
            message = _extract_opencode_go_error_message(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        pass

    if not message:
        return "OpenCode Go returned an unknown API error."
    return _sanitize_opencode_go_error_message(message)


def _extract_opencode_go_error_message(
    payload: dict[str, Any],
    *,
    raw_depth: int = 0,
) -> str | None:
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error

    top_level_message = payload.get("message")
    if isinstance(top_level_message, str) and top_level_message.strip():
        return top_level_message

    if not isinstance(error, dict):
        return None
    nested_message = error.get("message")
    if isinstance(nested_message, str) and nested_message.strip():
        return nested_message

    metadata = error.get("metadata")
    raw_error = metadata.get("raw") if isinstance(metadata, dict) else None
    if not isinstance(raw_error, str) or raw_depth >= 1:
        return None
    try:
        decoded_raw_error = json.loads(raw_error)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(decoded_raw_error, dict):
        return None
    return _extract_opencode_go_error_message(decoded_raw_error, raw_depth=raw_depth + 1)


def _sanitize_opencode_go_error_message(message: str) -> str:
    sanitized = " ".join(message.split())
    sanitized = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+",
        "Bearer [REDACTED]",
        sanitized,
    )
    sanitized = re.sub(
        r"(?i)\b(api[_ -]?key|access[_ -]?token|authorization|auth|token)"
        r"\s*[:=]\s*['\"]?[^\s,'\"]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(r"\bsk-[A-Za-z0-9._~+/=-]+", "[REDACTED]", sanitized)
    return sanitized[:OPENCODE_GO_ERROR_MESSAGE_LIMIT]


def _bounded_structure_keys(payload: dict[Any, Any]) -> list[str]:
    return sorted({str(key)[:64] for key in payload})[:20]


def _bounded_scalar(value: Any, limit: int) -> str | None:
    if not isinstance(value, (str, int, float, bool)):
        return None
    normalized = " ".join(str(value).split())
    return normalized[:limit] or None


def _build_opencode_go_rejection_diagnostic(
    req: Any,
    response: httpx.Response,
    request_payload: dict[str, Any],
    response_content: bytes,
) -> dict[str, Any]:
    response_payload: dict[str, Any] = {}
    try:
        parsed_response = json.loads(response_content)
        if isinstance(parsed_response, dict):
            response_payload = parsed_response
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        pass

    error_payload = response_payload.get("error")
    nested_error = error_payload if isinstance(error_payload, dict) else {}
    correlation_headers = {
        header_name: bounded_value
        for header_name in OPENCODE_GO_CORRELATION_HEADERS
        if (bounded_value := _bounded_scalar(response.headers.get(header_name), 256)) is not None
    }

    messages = request_payload.get("messages")
    request_messages = messages if isinstance(messages, list) else []
    role_counts: dict[str, int] = {}
    for message in request_messages:
        role = str(message.get("role") or "") if isinstance(message, dict) else ""
        normalized_role = role if role in {"system", "user", "assistant", "tool"} else "other"
        role_counts[normalized_role] = role_counts.get(normalized_role, 0) + 1

    input_items = request_payload.get("input")
    request_input = input_items if isinstance(input_items, list) else []
    input_role_counts: dict[str, int] = {}
    for item in request_input:
        role = str(item.get("role") or "") if isinstance(item, dict) else ""
        normalized_role = role if role in {"user", "assistant"} else "other"
        input_role_counts[normalized_role] = input_role_counts.get(normalized_role, 0) + 1

    tools = request_payload.get("tools")
    token_field = next(
        (
            field_name
            for field_name in ("max_tokens", "max_completion_tokens", "max_output_tokens")
            if field_name in request_payload
        ),
        None,
    )
    content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip()
    diagnostic = {
        "response_status": response.status_code,
        "response_content_type": content_type[:128],
        "response_byte_length": len(response_content),
        "response_top_level_keys": _bounded_structure_keys(response_payload),
        "response_error_keys": _bounded_structure_keys(nested_error),
        "response_error_type": _bounded_scalar(
            nested_error.get("type") or response_payload.get("type"), 128
        ),
        "response_error_code": _bounded_scalar(
            nested_error.get("code") or response_payload.get("code"), 128
        ),
        "response_correlation_headers": correlation_headers,
        "request_model": strip_model_prefix(req.model, OPENCODE_GO_MODEL_PREFIX)[:128],
        "request_payload_keys": _bounded_structure_keys(request_payload),
        "request_message_count": (len(request_messages) if "messages" in request_payload else None),
        "request_message_role_counts": (
            dict(sorted(role_counts.items())) if "messages" in request_payload else None
        ),
        "request_input_count": len(request_input) if "input" in request_payload else None,
        "request_input_role_counts": (
            dict(sorted(input_role_counts.items())) if "input" in request_payload else None
        ),
        "request_tool_count": len(tools) if isinstance(tools, list) else 0,
        "request_token_field": token_field,
    }
    return {key: value for key, value in diagnostic.items() if value is not None}


def _log_opencode_go_rejection(
    req: Any,
    response: httpx.Response,
    request_payload: dict[str, Any],
    response_content: bytes,
) -> None:
    diagnostic = _build_opencode_go_rejection_diagnostic(
        req,
        response,
        request_payload,
        response_content,
    )
    logger.warning("OpenCode Go request rejected: %s", json.dumps(diagnostic, sort_keys=True))


def _log_opencode_go_terminal_event(
    event_type: str,
    event_payload: dict[str, Any],
    event_counts: dict[str, int],
) -> None:
    response = event_payload.get("response")
    response_payload = response if isinstance(response, dict) else {}
    error = event_payload.get("error")
    if not isinstance(error, dict):
        response_error = response_payload.get("error")
        error = response_error if isinstance(response_error, dict) else {}
    incomplete = response_payload.get("incomplete_details")
    incomplete_payload = incomplete if isinstance(incomplete, dict) else {}
    output = response_payload.get("output")
    diagnostic = {
        "event_type": str(event_type)[:128],
        "event_keys": _bounded_structure_keys(event_payload),
        "response_keys": _bounded_structure_keys(response_payload),
        "error_type": _bounded_scalar(error.get("type"), 128),
        "error_code": _bounded_scalar(error.get("code"), 128),
        "response_status": _bounded_scalar(response_payload.get("status"), 128),
        "incomplete_reason": _bounded_scalar(incomplete_payload.get("reason"), 128),
        "output_count": len(output) if isinstance(output, list) else None,
        "event_counts": {
            str(key)[:128]: min(max(int(value), 0), 9999)
            for key, value in list(event_counts.items())[:20]
        },
    }
    logger.warning(
        "OpenCode Go Responses stream terminated: %s",
        json.dumps(
            {key: value for key, value in diagnostic.items() if value is not None},
            sort_keys=True,
        ),
    )


def _normalize_anthropic_usage_payload(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None

    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    prompt_tokens_details = {
        key: int(value or 0)
        for key, value in {
            "cache_creation": usage.get("cache_creation_input_tokens"),
            "cache_read": usage.get("cache_read_input_tokens"),
        }.items()
        if value is not None
    }

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "prompt_tokens_details": prompt_tokens_details,
        "completion_tokens_details": {},
        "cost_details": {},
    }


def _merge_usage_snapshots(
    previous: dict[str, Any] | None,
    new: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if new is None:
        return previous
    if previous is None:
        return new

    merged = dict(previous)
    for usage_field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if usage_field in new:
            merged[usage_field] = int(new[usage_field] or 0)
    for usage_field in ("prompt_tokens_details", "completion_tokens_details", "cost_details"):
        if usage_field in new:
            merged[usage_field] = dict(new[usage_field] or {})
    return merged


class OpenCodeGoReq:
    OPENAI_BASE_HEADERS = {
        "Content-Type": "application/json",
    }
    ANTHROPIC_BASE_HEADERS = {
        "Content-Type": "application/json",
        "anthropic-version": OPENCODE_GO_ANTHROPIC_VERSION,
    }

    def __init__(self, api_key: str, model: str, http_client=None):
        self.api_key = api_key
        self.opencode_go_api_key = api_key
        self.model = model
        self.http_client = http_client
        self.uses_anthropic_protocol = _uses_anthropic_protocol(model)
        self.uses_openai_responses_protocol = _uses_openai_responses_protocol(model)
        if self.uses_anthropic_protocol:
            self.api_url = OPENCODE_GO_ANTHROPIC_MESSAGES_URL
        elif self.uses_openai_responses_protocol:
            self.api_url = OPENCODE_GO_OPENAI_RESPONSES_URL
        else:
            self.api_url = OPENCODE_GO_OPENAI_CHAT_URL

    @property
    def headers(self) -> dict[str, str]:
        if self.uses_anthropic_protocol:
            return {**self.ANTHROPIC_BASE_HEADERS, "x-api-key": self.api_key}
        return {**self.OPENAI_BASE_HEADERS, "Authorization": f"Bearer {self.api_key}"}


@dataclass(kw_only=True)
class OpenCodeGoReqChat(BaseProviderReq, OpenCodeGoReq):
    api_key: str
    http_client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        OpenCodeGoReq.__init__(
            self, api_key=self.api_key, model=self.model, http_client=self.http_client
        )
        if self.http_client is None:
            raise ValueError("http_client must be provided")

    def validate_request(self) -> None:
        if self.schema is not None:
            raise ValueError("OpenCode Go models do not support structured-output helpers yet.")

        validate_supported_tools("OpenCode Go", self.selected_tools)

        if self.file_uuids or self.file_hashes or has_file_attachments(self.messages):
            raise ValueError(
                "OpenCode Go models do not support file or PDF attachments in Meridian yet."
            )

        if has_image_inputs(self.messages) and not _supports_image_inputs(self.model):
            raise ValueError("This OpenCode Go model does not support image inputs.")

        if not self.stream and self.selected_tools:
            raise ValueError("OpenCode Go tool execution requires streaming mode.")

        validate_http_client_for_tools("OpenCode Go", self.selected_tools, self.http_client)

    def get_payload(self) -> dict[str, Any]:
        if self.uses_anthropic_protocol:
            return self._get_anthropic_payload()
        openai_payload = self._get_openai_payload()
        if self.uses_openai_responses_protocol:
            return build_openai_responses_payload(openai_payload)
        return openai_payload

    def _get_openai_payload(self) -> dict[str, Any]:
        raw_messages = [
            normalize_openai_request_message(
                message,
                include_reasoning_content=_requires_reasoning_content_round_trip(self.model),
                include_tool_name=True,
                preserve_content_parts=_supports_image_inputs(self.model),
                strip_text=False,
            )
            for message in self.messages
            if isinstance(message, dict)
        ]
        available_tool_names = _normalize_selected_tool_names(self.selected_tools)
        sanitized_messages = sanitize_openai_messages(
            raw_messages,
            fallback_user_content=OPENCODE_GO_FALLBACK_USER_CONTENT,
            provider_label="OpenCode Go",
            preserve_empty_reasoning_content=_requires_reasoning_content_round_trip(self.model),
            preserve_content_parts=_supports_image_inputs(self.model),
        )
        authoritative_system_prompt = _build_opencode_go_authoritative_system_prompt(
            (
                sanitized_messages[0].get("content")
                if sanitized_messages and sanitized_messages[0].get("role") == "system"
                else None
            ),
            available_tool_names,
        )
        if sanitized_messages and sanitized_messages[0].get("role") == "system":
            sanitized_messages[0] = {"role": "system", "content": authoritative_system_prompt}
        else:
            sanitized_messages.insert(
                0,
                {"role": "system", "content": authoritative_system_prompt},
            )

        payload: dict[str, Any] = {
            "model": strip_model_prefix(self.model, OPENCODE_GO_MODEL_PREFIX),
            "messages": sanitized_messages,
            "stream": self.stream,
            "temperature": _resolve_temperature(
                self.model,
                getattr(self.config, "temperature", None),
            ),
            "top_p": _resolve_top_p(self.model, getattr(self.config, "top_p", None)),
            "max_tokens": normalize_max_tokens(getattr(self.config, "max_tokens", None)),
        }

        tools = get_openrouter_tools(
            self.selected_tools,
            include_image_inspection=(
                self.image_inspection_enabled and _supports_image_inputs(self.model)
            ),
        )
        if tools:
            payload["tools"] = tools

        return {key: value for key, value in payload.items() if value is not None}

    def _get_anthropic_payload(self) -> dict[str, Any]:
        raw_messages = [
            normalize_openai_request_message(
                message,
                include_tool_name=True,
                preserve_content_parts=_supports_image_inputs(self.model),
                strip_text=False,
            )
            for message in self.messages
            if isinstance(message, dict)
        ]
        available_tool_names = _normalize_selected_tool_names(self.selected_tools)
        system_prompt, anthropic_messages = build_anthropic_messages(raw_messages)
        if not anthropic_messages:
            anthropic_messages.append(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": OPENCODE_GO_FALLBACK_USER_CONTENT}],
                }
            )
        payload: dict[str, Any] = {
            "model": strip_model_prefix(self.model, OPENCODE_GO_MODEL_PREFIX),
            "messages": anthropic_messages,
            "stream": self.stream,
            "max_tokens": normalize_max_tokens(
                getattr(self.config, "max_tokens", None), fallback=8192
            ),
            "temperature": _resolve_temperature(
                self.model,
                getattr(self.config, "temperature", None),
            ),
            "top_p": _resolve_top_p(self.model, getattr(self.config, "top_p", None)),
        }

        payload["system"] = _build_opencode_go_authoritative_system_prompt(
            system_prompt,
            available_tool_names,
        )

        tools = _build_anthropic_tools(
            get_openrouter_tools(
                self.selected_tools,
                include_image_inspection=(
                    self.image_inspection_enabled and _supports_image_inputs(self.model)
                ),
            )
        )
        if tools:
            payload["tools"] = tools

        return {key: value for key, value in payload.items() if value is not None}


async def validate_opencode_go_api_key(
    api_key: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    payload = {
        "model": strip_model_prefix(OPENCODE_GO_VALIDATION_MODEL, OPENCODE_GO_MODEL_PREFIX),
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "max_tokens": 16,
    }

    async def _do_validate(client: httpx.AsyncClient) -> None:
        response = await client.post(
            OPENCODE_GO_OPENAI_CHAT_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        if response.status_code != 200:
            error_message = _parse_opencode_go_error(response.content)
            raise ValueError(
                f"OpenCode Go validation failed (status {response.status_code}): {error_message}"
            )

    if http_client is not None:
        await _do_validate(http_client)
        return

    async with httpx.AsyncClient(timeout=60.0, http2=True) as client:
        await _do_validate(client)


async def make_opencode_go_request_non_streaming(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if req.uses_anthropic_protocol:
        return await _make_opencode_go_anthropic_request_non_streaming(req, pg_engine)
    if req.uses_openai_responses_protocol:
        return await _make_opencode_go_responses_request_non_streaming(req, pg_engine)
    return await _make_opencode_go_openai_request_non_streaming(req, pg_engine)


async def _make_opencode_go_responses_request_non_streaming(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    with sentry_sdk.start_span(
        op="ai.request", description="OpenCode Go Responses request"
    ) as span:
        span.set_tag("chat.model", req.model)
        try:
            payload = req.get_payload()
            response = await client.post(
                req.api_url,
                headers=req.headers,
                json=payload,
                timeout=OPENCODE_GO_NON_STREAMING_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("OpenCode Go returned an invalid Responses payload.")
            status = str(data.get("status") or "completed")
            if status in {"failed", "incomplete"}:
                _log_opencode_go_terminal_event(
                    f"response.{status}", {"response": data}, {f"response.{status}": 1}
                )
                error_message = _extract_opencode_go_error_message(data)
                if error_message:
                    raise ValueError(_sanitize_opencode_go_error_message(error_message))
                raise ValueError("OpenCode Go returned an incomplete response.")
            output = data.get("output")
            if not isinstance(output, list):
                _log_opencode_go_terminal_event(
                    "invalid_output", {"response": data}, {"invalid_output": 1}
                )
                raise ValueError("OpenCode Go returned an invalid Responses output.")
            if extract_openai_responses_function_calls(output):
                _log_opencode_go_terminal_event(
                    "unexpected_function_call",
                    {"response": data},
                    {"unexpected_function_call": 1},
                )
                raise ValueError("OpenCode Go tool execution requires streaming mode.")
            content = extract_openai_responses_text(output)
            if not content:
                _log_opencode_go_terminal_event(
                    "empty_output", {"response": data}, {"empty_output": 1}
                )
                raise ValueError("OpenCode Go returned an empty Responses output.")

            usage_data = normalize_openai_responses_usage(data.get("usage"))
            if usage_data and req.graph_id and req.node_id and not req.is_title_generation:
                await update_node_usage_data(
                    pg_engine=pg_engine,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    usage_data=usage_data,
                    node_type=req.node_type,
                    model_id=req.model_id,
                )
            return content
        except HTTPStatusError as exc:
            error_message = _parse_opencode_go_error(exc.response.content)
            _log_opencode_go_rejection(req, exc.response, payload, exc.response.content)
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {exc.response.status_code}): {error_message}"
            ) from exc
        except ValueError:
            span.set_status("internal_error")
            raise
        except (ConnectError, TimeoutException, AsyncTimeoutError) as exc:
            logger.error("Network/Timeout error connecting to OpenCode Go: %s", exc)
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from exc
        except Exception as exc:
            logger.error("Unexpected OpenCode Go Responses error: %s", exc, exc_info=True)
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from exc


async def _make_opencode_go_openai_request_non_streaming(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    with sentry_sdk.start_span(op="ai.request", description="OpenCode Go request") as span:
        span.set_tag("chat.model", req.model)
        try:
            payload = req.get_payload()
            response = await client.post(
                req.api_url,
                headers=req.headers,
                json=payload,
                timeout=OPENCODE_GO_NON_STREAMING_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
            if message.get("tool_calls"):
                raise ValueError("OpenCode Go tool execution requires streaming mode.")

            content = str(message.get("content") or "")
            if usage_data := data.get("usage"):
                if req.graph_id and req.node_id and not req.is_title_generation:
                    await update_node_usage_data(
                        pg_engine=pg_engine,
                        graph_id=req.graph_id,
                        node_id=req.node_id,
                        usage_data=usage_data,
                        node_type=req.node_type,
                        model_id=req.model_id,
                    )

            return content
        except HTTPStatusError as exc:
            error_message = _parse_opencode_go_error(exc.response.content)
            _log_opencode_go_rejection(
                req,
                exc.response,
                payload,
                exc.response.content,
            )
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {exc.response.status_code}): {error_message}"
            ) from exc
        except (ConnectError, TimeoutException, AsyncTimeoutError) as exc:
            logger.error("Network/Timeout error connecting to OpenCode Go: %s", exc)
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected error during OpenCode Go request: %s",
                exc,
                exc_info=True,
            )
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from exc


async def _make_opencode_go_anthropic_request_non_streaming(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    with sentry_sdk.start_span(
        op="ai.request", description="OpenCode Go anthropic request"
    ) as span:
        span.set_tag("chat.model", req.model)
        try:
            payload = req.get_payload()
            response = await client.post(
                req.api_url,
                headers=req.headers,
                json=payload,
                timeout=OPENCODE_GO_NON_STREAMING_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()
            content_blocks = data.get("content") or []
            content_parts: list[str] = []
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    raise ValueError("OpenCode Go tool execution requires streaming mode.")
                if block.get("type") == "text" and block.get("text"):
                    content_parts.append(str(block["text"]))

            usage_data = _normalize_anthropic_usage_payload(data.get("usage"))
            if usage_data and req.graph_id and req.node_id and not req.is_title_generation:
                await update_node_usage_data(
                    pg_engine=pg_engine,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    usage_data=usage_data,
                    node_type=req.node_type,
                    model_id=req.model_id,
                )

            return "".join(content_parts)
        except HTTPStatusError as exc:
            error_message = _parse_anthropic_error(exc.response.content)
            logger.error(
                "HTTP error from OpenCode Go (Anthropic protocol): %s - %s",
                exc.response.status_code,
                error_message,
            )
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {exc.response.status_code}): {error_message}"
            ) from exc
        except (ConnectError, TimeoutException, AsyncTimeoutError) as exc:
            logger.error("Network/Timeout error connecting to OpenCode Go: %s", exc)
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected error during OpenCode Go anthropic request: %s",
                exc,
                exc_info=True,
            )
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from exc


async def stream_opencode_go_response(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()
    if req.uses_anthropic_protocol:
        async for chunk in _stream_opencode_go_anthropic_response(
            req,
            pg_engine,
            redis_manager,
            final_data_container,
        ):
            yield chunk
        return

    if req.uses_openai_responses_protocol:
        async for chunk in _stream_opencode_go_responses_response(
            req,
            pg_engine,
            redis_manager,
            final_data_container,
        ):
            yield chunk
        return

    async for chunk in _stream_opencode_go_openai_response(
        req,
        pg_engine,
        redis_manager,
        final_data_container,
    ):
        yield chunk


async def _stream_opencode_go_openai_response(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    async for chunk in stream_openai_compatible_response(
        req,
        pg_engine,
        redis_manager,
        provider_label="OpenCode Go",
        error_parser=_parse_opencode_go_error,
        final_data_container=final_data_container,
        span_description="Stream OpenCode Go response",
        rejected_response_observer=_log_opencode_go_rejection,
        preserve_reasoning_content=_requires_reasoning_content_round_trip(req.model),
    ):
        yield chunk


async def _stream_opencode_go_responses_response(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    async for chunk in stream_openai_responses_response(
        req,
        pg_engine,
        redis_manager,
        provider_label="OpenCode Go",
        error_parser=_parse_opencode_go_error,
        error_sanitizer=_sanitize_opencode_go_error_message,
        final_data_container=final_data_container,
        span_description="Stream OpenCode Go Responses response",
        rejected_response_observer=_log_opencode_go_rejection,
        terminal_event_observer=_log_opencode_go_terminal_event,
    ):
        yield chunk


@dataclass
class _OpenCodeGoAnthropicRoundState:
    usage_data: dict[str, Any] | None = None
    request_id: str | None = None
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    tool_calls_by_index: dict[int, dict[str, Any]] = field(default_factory=dict)
    content_block_types: dict[int, str] = field(default_factory=dict)


@dataclass
class _OpenCodeGoAnthropicStreamState:
    messages: list[dict[str, Any]]
    full_response: str = ""
    clean_content: str = ""
    thinking_started: bool = False
    usage_data: dict[str, Any] | None = None
    request_index: int = 0
    round_state: _OpenCodeGoAnthropicRoundState = field(
        default_factory=_OpenCodeGoAnthropicRoundState
    )

    def start_round(self) -> None:
        self.round_state = _OpenCodeGoAnthropicRoundState()


@dataclass
class _OpenCodeGoAnthropicEventResult:
    chunks: list[str] = field(default_factory=list)
    should_break_stream: bool = False
    should_return: bool = False


class _OpenCodeGoAnthropicEventDispatcher:
    def __init__(self, state: _OpenCodeGoAnthropicStreamState):
        self.state = state
        self._handlers = {
            "error": self._handle_error,
            "message_start": self._handle_message_start,
            "content_block_start": self._handle_content_block_start,
            "content_block_delta": self._handle_content_block_delta,
            "content_block_stop": self._handle_content_block_stop,
            "message_delta": self._handle_message_delta,
            "message_stop": self._handle_message_stop,
        }

    def dispatch(
        self,
        event_type: str,
        event_payload: dict[str, Any],
        *,
        data_str: str,
    ) -> _OpenCodeGoAnthropicEventResult:
        handler = self._handlers.get(event_type)
        if handler is None:
            return _OpenCodeGoAnthropicEventResult()
        return handler(event_payload, data_str=data_str)

    def _handle_error(
        self, _event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        return _OpenCodeGoAnthropicEventResult(
            chunks=[f"[ERROR]{_parse_anthropic_error(data_str.encode('utf-8'))}[!ERROR]"],
            should_return=True,
        )

    def _handle_message_start(
        self, event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        message_payload = event_payload.get("message")
        if isinstance(message_payload, dict):
            if message_payload.get("id") and self.state.round_state.request_id is None:
                self.state.round_state.request_id = str(message_payload["id"])
            self.state.round_state.usage_data = _merge_usage_snapshots(
                self.state.round_state.usage_data,
                _normalize_anthropic_usage_payload(message_payload.get("usage")),
            )
        return _OpenCodeGoAnthropicEventResult()

    def _handle_content_block_start(
        self, event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        index = int(event_payload.get("index", 0) or 0)
        content_block = event_payload.get("content_block")
        if not isinstance(content_block, dict):
            return _OpenCodeGoAnthropicEventResult()

        block_type = str(content_block.get("type") or "")
        self.state.round_state.content_block_types[index] = block_type
        if block_type == "text" and content_block.get("text"):
            text = str(content_block["text"])
            self.state.clean_content += text
            self.state.full_response += text
            return _OpenCodeGoAnthropicEventResult(chunks=[text])
        if block_type == "tool_use":
            self.state.round_state.tool_calls_by_index[index] = {
                "id": str(content_block.get("id") or f"call_{uuid.uuid4().hex}"),
                "function": {
                    "name": str(content_block.get("name") or "").strip(),
                    "arguments": serialize_anthropic_tool_input(content_block.get("input")),
                },
            }
        return _OpenCodeGoAnthropicEventResult()

    def _handle_content_block_delta(
        self, event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        index = int(event_payload.get("index", 0) or 0)
        delta = event_payload.get("delta")
        if not isinstance(delta, dict):
            return _OpenCodeGoAnthropicEventResult()

        delta_type = str(delta.get("type") or "")
        if delta_type == "text_delta" and delta.get("text"):
            text = str(delta["text"])
            self.state.clean_content += text
            self.state.full_response += text
            return _OpenCodeGoAnthropicEventResult(chunks=[text])
        if delta_type == "thinking_delta" and delta.get("thinking"):
            chunks: list[str] = []
            if not self.state.thinking_started:
                chunks.append("[THINK]\n")
                self.state.thinking_started = True
            chunks.append(str(delta["thinking"]))
            return _OpenCodeGoAnthropicEventResult(chunks=chunks)
        if delta_type == "input_json_delta" and delta.get("partial_json"):
            tool_call = self.state.round_state.tool_calls_by_index.setdefault(
                index,
                {
                    "id": f"call_{uuid.uuid4().hex}",
                    "function": {"name": "", "arguments": ""},
                },
            )
            tool_call["function"]["arguments"] += str(delta["partial_json"])
        return _OpenCodeGoAnthropicEventResult()

    def _handle_content_block_stop(
        self, event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        index = int(event_payload.get("index", 0) or 0)
        if (
            self.state.round_state.content_block_types.get(index) == "thinking"
            and self.state.thinking_started
        ):
            self.state.thinking_started = False
            return _OpenCodeGoAnthropicEventResult(chunks=["\n[!THINK]\n"])
        return _OpenCodeGoAnthropicEventResult()

    def _handle_message_delta(
        self, event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        delta = event_payload.get("delta")
        if isinstance(delta, dict):
            self.state.round_state.native_finish_reason = (
                str(delta.get("stop_reason") or "") or None
            )
            if self.state.round_state.native_finish_reason == "tool_use":
                self.state.round_state.finish_reason = "tool_calls"
            elif self.state.round_state.native_finish_reason:
                self.state.round_state.finish_reason = "stop"

        self.state.round_state.usage_data = _merge_usage_snapshots(
            self.state.round_state.usage_data,
            _normalize_anthropic_usage_payload(event_payload.get("usage")),
        )
        return _OpenCodeGoAnthropicEventResult()

    def _handle_message_stop(
        self, event_payload: dict[str, Any], *, data_str: str
    ) -> _OpenCodeGoAnthropicEventResult:
        self.state.round_state.finish_reason = self.state.round_state.finish_reason or "stop"
        return _OpenCodeGoAnthropicEventResult(should_break_stream=True)


def _parse_anthropic_sse_event(raw_event: str) -> tuple[str, str, dict[str, Any] | None]:
    event_type: str | None = None
    data_lines: list[str] = []
    for raw_line in raw_event.splitlines():
        line = raw_line.strip()
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())

    data_str = "\n".join(data_lines).strip() if data_lines else raw_event.strip()
    if not data_str:
        return event_type or "message", data_str, None

    try:
        event_payload = json.loads(data_str)
    except json.JSONDecodeError:
        return event_type or "message", data_str, None
    if not isinstance(event_payload, dict):
        return event_type or "message", data_str, None

    return event_type or str(event_payload.get("type") or "message"), data_str, event_payload


async def _stream_opencode_go_anthropic_response(
    req: OpenCodeGoReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    state = _OpenCodeGoAnthropicStreamState(messages=req.messages.copy())
    dispatcher = _OpenCodeGoAnthropicEventDispatcher(state)

    try:
        while True:
            state.start_round()
            request_payload = req.get_payload()

            async with client.stream(
                "POST",
                req.api_url,
                headers=req.headers,
                json=request_payload,
            ) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    error_message = _parse_anthropic_error(error_content)
                    yield (
                        "[ERROR]Stream Error: Failed to get response from OpenCode Go "
                        f"(Status: {response.status_code}). \n{error_message}[!ERROR]"
                    )
                    return

                with sentry_sdk.start_span(
                    op="ai.streaming",
                    description="Stream OpenCode Go anthropic response",
                ) as span:
                    span.set_tag("chat.model", req.model)
                    buffer = ""

                    async for byte_chunk in response.aiter_bytes():
                        buffer += byte_chunk.decode("utf-8", errors="ignore")

                        while "\n\n" in buffer:
                            raw_event, buffer = buffer.split("\n\n", 1)
                            if not raw_event.strip():
                                continue

                            event_type, data_str, event_payload = _parse_anthropic_sse_event(
                                raw_event
                            )
                            if event_payload is None:
                                continue

                            event_result = dispatcher.dispatch(
                                event_type,
                                event_payload,
                                data_str=data_str,
                            )
                            for chunk in event_result.chunks:
                                yield chunk
                            if event_result.should_return:
                                return
                            if event_result.should_break_stream:
                                break

                        if state.round_state.finish_reason:
                            break

                    if state.thinking_started:
                        yield "\n[!THINK]\n"
                        state.thinking_started = False

                    span.set_data("response_length", len(state.full_response))

            if state.round_state.usage_data and not req.is_title_generation:
                state.request_index += 1
                state.usage_data = append_usage_request_breakdown(
                    state.usage_data,
                    build_usage_request_breakdown(
                        usage_data=state.round_state.usage_data,
                        index=state.request_index,
                        model=req.model,
                        finish_reason=state.round_state.finish_reason,
                        native_finish_reason=state.round_state.native_finish_reason,
                        request_id=state.round_state.request_id,
                        tool_names=(
                            extract_tool_names(
                                anthropic_tool_calls_to_openai(
                                    state.round_state.tool_calls_by_index
                                )
                            )
                            if state.round_state.finish_reason == "tool_calls"
                            else []
                        ),
                    ),
                )

            if state.round_state.finish_reason == "tool_calls":
                tool_calls = anthropic_tool_calls_to_openai(state.round_state.tool_calls_by_index)
                continuation = await _process_tool_calls_and_continue(
                    tool_calls,
                    state.messages,
                    req,
                    redis_manager,
                    assistant_content=state.clean_content if state.clean_content else None,
                )
                state.messages = continuation.messages
                req = continuation.req

                for feedback in continuation.feedback_strings:
                    yield feedback

                if continuation.pending_tool_call_id and final_data_container is not None:
                    final_data_container["pending_tool_call_id"] = continuation.pending_tool_call_id

                if continuation.should_continue:
                    state.full_response = ""
                    state.clean_content = ""
                    continue
                if continuation.awaiting_user_input:
                    break
                break

            break

        usage_data = finalize_usage_data(state.usage_data)

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
        logger.info("Stream for node %s was cancelled by the connection manager.", req.node_id)
        raise
    except ConnectError as exc:
        logger.error("Network connection error to OpenCode Go: %s", exc)
        yield (
            "[ERROR]Connection Error: Could not connect to the API. "
            "Please check your network.[!ERROR]"
        )
    except (TimeoutException, AsyncTimeoutError) as exc:
        logger.error("Request to OpenCode Go timed out: %s", exc)
        yield "[ERROR]Timeout: The request to the AI model took too long to respond.[!ERROR]"
    except HTTPStatusError as exc:
        logger.error(
            "HTTP error from OpenCode Go: %s - %s",
            exc.response.status_code,
            exc.response.text,
        )
        yield (
            "[ERROR]HTTP Error: Received an invalid response from the server "
            f"(Status: {exc.response.status_code}).[!ERROR]"
        )
    except Exception as exc:
        logger.error(
            "Unexpected error during OpenCode Go anthropic streaming: %s",
            exc,
            exc_info=True,
        )
        yield "[ERROR]An unexpected server error occurred. Please try again later.[!ERROR]"
