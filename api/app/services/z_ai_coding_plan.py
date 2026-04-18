import asyncio
import json
import logging
from asyncio import TimeoutError as AsyncTimeoutError
from enum import Enum
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from models.message import MessageContentTypeEnum, NodeTypeEnum, ToolEnum
from pydantic import BaseModel
from services.openrouter import _parse_openrouter_error, _process_tool_calls_and_continue
from services.providers.z_ai_coding_plan_catalog import Z_AI_CODING_PLAN_MODEL_PREFIX
from services.sandbox_inputs import SandboxInputFileReference
from services.tools import get_openrouter_tools
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

Z_AI_CODING_PLAN_CHAT_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
Z_AI_CODING_PLAN_VALIDATION_MODEL = f"{Z_AI_CODING_PLAN_MODEL_PREFIX}glm-5.1"
Z_AI_CODING_PLAN_NON_STREAMING_TIMEOUT = httpx.Timeout(300.0, connect=10.0, read=300.0)
Z_AI_CODING_PLAN_SUPPORTED_TOOLS = {
    ToolEnum.WEB_SEARCH,
    ToolEnum.LINK_EXTRACTION,
    ToolEnum.EXECUTE_CODE,
    ToolEnum.IMAGE_GENERATION,
    ToolEnum.VISUALISE,
    ToolEnum.ASK_USER,
}
Z_AI_TOOL_CALL_PLACEHOLDER_CONTENT = "[Tool call issued]"
Z_AI_FALLBACK_USER_CONTENT = "Please respond to the available context."


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == MessageContentTypeEnum.text.value and item.get("text"):
            parts.append(str(item["text"]))
    return "\n".join(part for part in parts if part)


def _normalize_role_value(role: Any) -> str:
    if isinstance(role, Enum):
        normalized = str(role.value or "").strip()
    elif isinstance(role, str):
        normalized = role.strip()
    else:
        normalized = str(role or "").strip()

    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]

    return normalized.lower() or "user"


def _model_alias(model_id: str) -> str:
    if model_id.startswith(Z_AI_CODING_PLAN_MODEL_PREFIX):
        return model_id[len(Z_AI_CODING_PLAN_MODEL_PREFIX) :]
    return model_id


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


def _build_thinking_payload(config: Any, is_title_generation: bool) -> dict[str, str]:
    if is_title_generation or bool(getattr(config, "exclude_reasoning", False)):
        return {"type": "disabled"}
    return {"type": "enabled"}


def _normalize_temperature(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(parsed, 1.0))


def _normalize_top_p(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return 0.01
    return max(0.01, min(parsed, 1.0))


def _normalize_max_tokens(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return min(parsed, 131072)


def _normalize_message_for_z_ai(message: dict[str, Any]) -> dict[str, Any]:
    role = _normalize_role_value(message.get("role"))
    normalized: dict[str, Any] = {"role": role}

    if "content" in message:
        content = message.get("content")
        normalized["content"] = (
            content if isinstance(content, str) else _extract_text_content(content)
        )

    if role == "assistant":
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            normalized["tool_calls"] = tool_calls
        reasoning_content = message.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content:
            normalized["reasoning_content"] = reasoning_content

    if role == "tool":
        tool_call_id = message.get("tool_call_id")
        if isinstance(tool_call_id, str) and tool_call_id:
            normalized["tool_call_id"] = tool_call_id

    return normalized


def _sanitize_z_ai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    leading_system_message: dict[str, Any] | None = None
    seen_user_message = False
    pending_tool_call_ids: set[str] = set()

    for message in messages:
        role = str(message.get("role") or "")
        if role not in {"system", "user", "assistant", "tool"}:
            continue

        if role == "system":
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            if leading_system_message is None:
                leading_system_message = {"role": "system", "content": content}
            continue

        if role == "user":
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            seen_user_message = True
            pending_tool_call_ids.clear()
            sanitized.append({"role": "user", "content": content})
            continue

        if not seen_user_message:
            continue

        if role == "assistant":
            content = str(message.get("content") or "")
            tool_calls = message.get("tool_calls")
            reasoning_content = message.get("reasoning_content")

            normalized_assistant: dict[str, Any] = {
                "role": "assistant",
                "content": content,
            }

            if isinstance(reasoning_content, str) and reasoning_content:
                normalized_assistant["reasoning_content"] = reasoning_content

            next_pending_tool_call_ids: set[str] = set()
            if isinstance(tool_calls, list) and tool_calls:
                normalized_assistant["tool_calls"] = tool_calls
                if not content.strip():
                    normalized_assistant["content"] = Z_AI_TOOL_CALL_PLACEHOLDER_CONTENT
                next_pending_tool_call_ids = {
                    str(tool_call.get("id") or "")
                    for tool_call in tool_calls
                    if isinstance(tool_call, dict) and str(tool_call.get("id") or "")
                }

            if not content.strip() and "tool_calls" not in normalized_assistant:
                continue

            pending_tool_call_ids = next_pending_tool_call_ids
            sanitized.append(normalized_assistant)
            continue

        tool_call_id = str(message.get("tool_call_id") or "")
        content = str(message.get("content") or "").strip()
        if not tool_call_id or not content:
            continue
        if pending_tool_call_ids and tool_call_id not in pending_tool_call_ids:
            continue

        sanitized.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            }
        )

    if leading_system_message is not None:
        sanitized.insert(0, leading_system_message)

    if not any(str(message.get("role") or "") == "user" for message in sanitized):
        logger.warning(
            "Z.AI Coding Plan request had no usable user message after sanitization; "
            "injecting fallback user content."
        )
        sanitized.append({"role": "user", "content": Z_AI_FALLBACK_USER_CONTENT})

    return sanitized


class ZAiCodingPlanReq:
    BASE_HEADERS = {
        "Content-Type": "application/json",
    }

    def __init__(
        self,
        api_key: str,
        api_url: str = Z_AI_CODING_PLAN_CHAT_URL,
        http_client=None,
    ):
        self.api_key = api_key
        self.z_ai_api_key = api_key
        self.headers = {**self.BASE_HEADERS, "Authorization": f"Bearer {api_key}"}
        self.api_url = api_url
        self.http_client = http_client


class ZAiCodingPlanReqChat(ZAiCodingPlanReq):
    def __init__(
        self,
        api_key: str,
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
        http_client: Optional[httpx.AsyncClient] = None,
        file_uuids: Optional[list[str]] = None,
        file_hashes: Optional[dict[str, str]] = None,
        pdf_engine: str = "default",
        selected_tools: Optional[list[ToolEnum]] = None,
        sandbox_input_files: Optional[list[SandboxInputFileReference]] = None,
        sandbox_input_warnings: Optional[list[str]] = None,
    ):
        super().__init__(api_key=api_key, http_client=http_client)
        self.model = model
        self.model_id = model_id
        raw_messages = [
            mess.model_dump(exclude_none=True) if hasattr(mess, "model_dump") else mess
            for mess in messages
        ]
        normalized_messages = [
            _normalize_message_for_z_ai(raw_message) for raw_message in raw_messages
        ]
        self.messages = _sanitize_z_ai_messages(normalized_messages)
        self.config = config
        self.user_id = user_id
        self.pg_engine = pg_engine
        self.node_id = node_id
        self.graph_id = graph_id
        self.is_title_generation = is_title_generation
        self.node_type = node_type
        self.schema = schema
        self.stream = stream
        self.file_uuids = file_uuids or []
        self.file_hashes = file_hashes or {}
        self.pdf_engine = pdf_engine
        self.selected_tools = selected_tools or []
        self.sandbox_input_files = sandbox_input_files or []
        self.sandbox_input_warnings = sandbox_input_warnings or []

        if http_client is None:
            raise ValueError("http_client must be provided")
        self.http_client = http_client

    def validate_request(self) -> None:
        if self.schema is not None:
            raise ValueError(
                "Z.AI Coding Plan models do not support structured-output helpers yet."
            )

        unsupported_tools = [
            tool.value
            for tool in self.selected_tools
            if tool not in Z_AI_CODING_PLAN_SUPPORTED_TOOLS
        ]
        if unsupported_tools:
            unsupported = ", ".join(unsupported_tools)
            raise ValueError(
                "Z.AI Coding Plan models currently support only these Meridian tools: "
                "web_search, link_extraction, execute_code, image_generation, visualise, ask_user. "
                f"Unsupported selection: {unsupported}."
            )

        if self.file_uuids or self.file_hashes or _has_file_attachments(self.messages):
            raise ValueError(
                "Z.AI Coding Plan models do not support attachments or PDF parsing yet."
            )

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
                "Z.AI Coding Plan tool execution requires an HTTP client in this request."
            )

    def get_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": _model_alias(self.model),
            "messages": self.messages,
            "stream": self.stream,
            "temperature": _normalize_temperature(getattr(self.config, "temperature", None)),
            "top_p": _normalize_top_p(getattr(self.config, "top_p", None)),
            "max_tokens": _normalize_max_tokens(getattr(self.config, "max_tokens", None)),
            "thinking": _build_thinking_payload(self.config, self.is_title_generation),
        }

        tools = get_openrouter_tools(self.selected_tools)
        if tools:
            payload["tools"] = tools

        return {key: value for key, value in payload.items() if value is not None}


def _extract_text_delta(
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


async def validate_z_ai_coding_plan_api_key(
    api_key: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    payload = {
        "model": _model_alias(Z_AI_CODING_PLAN_VALIDATION_MODEL),
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "max_tokens": 16,
        "thinking": {"type": "disabled"},
    }

    async def _do_validate(client: httpx.AsyncClient) -> None:
        response = await client.post(
            Z_AI_CODING_PLAN_CHAT_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        if response.status_code != 200:
            error_message = _parse_openrouter_error(response.content)
            raise ValueError(
                f"Z.AI Coding Plan validation failed (status {response.status_code}): "
                f"{error_message}"
            )

    if http_client is not None:
        await _do_validate(http_client)
        return

    async with httpx.AsyncClient(timeout=60.0, http2=True) as client:
        await _do_validate(client)


async def make_z_ai_coding_plan_request_non_streaming(
    req: ZAiCodingPlanReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if ToolEnum.ASK_USER in req.selected_tools:
        raise ValueError("Z.AI Coding Plan ask_user requires streaming mode.")

    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    with sentry_sdk.start_span(op="ai.request", description="Z.AI Coding Plan request") as span:
        span.set_tag("chat.model", req.model)
        try:
            response = await client.post(
                req.api_url,
                headers=req.headers,
                json=req.get_payload(),
                timeout=Z_AI_CODING_PLAN_NON_STREAMING_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
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
            error_message = _parse_openrouter_error(exc.response.content)
            logger.error(
                "HTTP error from Z.AI Coding Plan: %s - %s",
                exc.response.status_code,
                error_message,
            )
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {exc.response.status_code}): {error_message}"
            ) from exc
        except (ConnectError, TimeoutException, AsyncTimeoutError) as exc:
            logger.error("Network/Timeout error connecting to Z.AI Coding Plan: %s", exc)
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from exc
        except Exception as exc:
            logger.error(
                "An unexpected error occurred during Z.AI Coding Plan request: %s",
                exc,
                exc_info=True,
            )
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from exc


async def stream_z_ai_coding_plan_response(
    req: ZAiCodingPlanReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()

    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    full_response = ""
    clean_content = ""
    thinking_started = False
    usage_data: dict[str, Any] = {}
    messages = req.messages.copy()

    try:
        while True:
            async with client.stream(
                "POST",
                req.api_url,
                headers=req.headers,
                json=req.get_payload(),
            ) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    error_message = _parse_openrouter_error(error_content)
                    logger.error(
                        "Z.AI Coding Plan rejected request with messages=%s",
                        [
                            {
                                "role": str(message.get("role") or ""),
                                "content_length": len(str(message.get("content") or "")),
                                "has_tool_calls": bool(message.get("tool_calls")),
                                "tool_call_id": str(message.get("tool_call_id") or ""),
                            }
                            for message in req.messages
                        ],
                    )
                    yield (
                        "[ERROR]Stream Error: Failed to get response from Z.AI Coding Plan "
                        f"(Status: {response.status_code}). \n{error_message}[!ERROR]"
                    )
                    return

                with sentry_sdk.start_span(
                    op="ai.streaming",
                    description="Stream Z.AI Coding Plan response",
                ) as span:
                    span.set_tag("chat.model", req.model)
                    buffer = ""
                    tool_call_chunks: list[dict[str, Any]] = []
                    finish_reason: str | None = None

                    async for byte_chunk in response.aiter_bytes():
                        buffer += byte_chunk.decode("utf-8", errors="ignore")
                        lines = buffer.splitlines(keepends=True)

                        if lines and not lines[-1].endswith(("\n", "\r")):
                            buffer = lines.pop()
                        else:
                            buffer = ""

                        for line in lines:
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue

                            data_str = line[len("data: ") :].strip()
                            if data_str == "[DONE]":
                                if thinking_started:
                                    yield "\n[!THINK]\n"
                                    thinking_started = False
                                finish_reason = "stop"
                                break

                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if new_usage := chunk.get("usage"):
                                usage_data = new_usage

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            choice = choices[0]
                            delta = choice.get("delta", {})

                            if "tool_calls" in delta:
                                tool_call_chunks.extend(delta["tool_calls"])

                            if choice.get("finish_reason") == "tool_calls":
                                if thinking_started:
                                    yield "\n[!THINK]\n"
                                    thinking_started = False
                                finish_reason = "tool_calls"
                                break

                            if delta.get("content"):
                                clean_content += str(delta["content"])

                            content, thinking_started = _extract_text_delta(
                                delta,
                                thinking_started=thinking_started,
                            )
                            if content:
                                full_response += content
                                yield content

                        if finish_reason:
                            break

                    span.set_data("response_length", len(full_response))

            if finish_reason == "tool_calls":
                (
                    should_continue,
                    messages,
                    req,
                    _,
                    feedback_strings,
                    awaiting_user_input,
                    pending_tool_call_id,
                ) = await _process_tool_calls_and_continue(
                    tool_call_chunks,
                    messages,
                    req,
                    redis_manager,
                    assistant_content=clean_content if clean_content else None,
                )

                for feedback in feedback_strings:
                    yield feedback

                if pending_tool_call_id and final_data_container is not None:
                    final_data_container["pending_tool_call_id"] = pending_tool_call_id

                if should_continue:
                    full_response = ""
                    clean_content = ""
                    continue
                if awaiting_user_input:
                    break
                break

            break

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
        logger.error("Network connection error to Z.AI Coding Plan: %s", exc)
        yield (
            "[ERROR]Connection Error: Could not connect to the API. "
            "Please check your network.[!ERROR]"
        )
    except (TimeoutException, AsyncTimeoutError) as exc:
        logger.error("Request to Z.AI Coding Plan timed out: %s", exc)
        yield "[ERROR]Timeout: The request to the AI model took too long to respond.[!ERROR]"
    except HTTPStatusError as exc:
        logger.error(
            "HTTP error from Z.AI Coding Plan: %s - %s",
            exc.response.status_code,
            exc.response.text,
        )
        yield (
            "[ERROR]HTTP Error: Received an invalid response from the server "
            f"(Status: {exc.response.status_code}).[!ERROR]"
        )
    except Exception as exc:
        logger.error(
            "An unexpected error occurred during Z.AI Coding Plan streaming: %s",
            exc,
            exc_info=True,
        )
        yield "[ERROR]An unexpected server error occurred. Please try again later.[!ERROR]"
