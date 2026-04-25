import asyncio
import json
import logging
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterator, Callable
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from services.openrouter import _merge_tool_call_chunks, _process_tool_calls_and_continue
from services.providers.common import (
    extract_reasoning_text_delta,
    extract_text_content,
    normalize_role_value,
)
from services.usage_data import (
    append_usage_request_breakdown,
    build_usage_request_breakdown,
    extract_tool_names,
    finalize_usage_data,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


def normalize_openai_request_message(
    message: dict[str, Any],
    *,
    include_reasoning_content: bool = False,
    include_tool_name: bool = False,
    strip_text: bool = False,
) -> dict[str, Any]:
    role = normalize_role_value(message.get("role"))
    normalized: dict[str, Any] = {"role": role}

    if "content" in message:
        content = message.get("content")
        normalized["content"] = (
            content if isinstance(content, str) else extract_text_content(content, strip=strip_text)
        )

    if role == "assistant":
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            normalized["tool_calls"] = tool_calls
        if include_reasoning_content:
            reasoning_content = message.get("reasoning_content")
            if isinstance(reasoning_content, str):
                normalized["reasoning_content"] = reasoning_content

    if role == "tool":
        tool_call_id = message.get("tool_call_id")
        if isinstance(tool_call_id, str) and tool_call_id:
            normalized["tool_call_id"] = tool_call_id
        if include_tool_name:
            name = str(message.get("name") or "").strip()
            if name:
                normalized["name"] = name

    return normalized


def sanitize_openai_messages(
    messages: list[dict[str, Any]],
    *,
    fallback_user_content: str,
    provider_label: str,
    tool_call_placeholder_content: str | None = None,
    preserve_empty_reasoning_content: bool = False,
) -> list[dict[str, Any]]:
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
            if isinstance(reasoning_content, str) and (
                reasoning_content or preserve_empty_reasoning_content
            ):
                normalized_assistant["reasoning_content"] = reasoning_content

            next_pending_tool_call_ids: set[str] = set()
            if isinstance(tool_calls, list) and tool_calls:
                normalized_assistant["tool_calls"] = tool_calls
                if not content.strip() and tool_call_placeholder_content is not None:
                    normalized_assistant["content"] = tool_call_placeholder_content
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
            "%s request had no usable user message after sanitization; "
            "injecting fallback user content.",
            provider_label,
        )
        sanitized.append({"role": "user", "content": fallback_user_content})

    return sanitized


async def iter_openai_sse_payloads(
    response: httpx.Response,
) -> AsyncIterator[dict[str, Any] | None]:
    buffer = ""
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
                yield None
                continue

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if isinstance(chunk, dict):
                yield chunk


async def stream_openai_compatible_response(
    req: Any,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    *,
    provider_label: str,
    error_parser: Callable[[bytes], str],
    final_data_container: Optional[dict[str, Any]] = None,
    span_description: str,
    on_rejected_request: Callable[[Any], None] | None = None,
    preserve_reasoning_content: bool = False,
) -> AsyncIterator[str]:
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    full_response = ""
    clean_content = ""
    thinking_started = False
    usage_data: dict[str, Any] | None = None
    messages = req.messages.copy()
    request_index = 0

    try:
        while True:
            round_usage_data: dict[str, Any] | None = None
            round_request_id: str | None = None
            native_finish_reason: str | None = None
            round_reasoning_content = ""
            payload = req.get_payload()

            async with client.stream(
                "POST",
                req.api_url,
                headers=req.headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    error_message = error_parser(error_content)
                    if on_rejected_request is not None:
                        on_rejected_request(req)
                    yield (
                        f"[ERROR]Stream Error: Failed to get response from {provider_label} "
                        f"(Status: {response.status_code}). \n{error_message}[!ERROR]"
                    )
                    return

                with sentry_sdk.start_span(
                    op="ai.streaming",
                    description=span_description,
                ) as span:
                    span.set_tag("chat.model", req.model)
                    tool_call_chunks: list[dict[str, Any]] = []
                    finish_reason: str | None = None

                    async for chunk in iter_openai_sse_payloads(response):
                        if chunk is None:
                            if thinking_started:
                                yield "\n[!THINK]\n"
                                thinking_started = False
                            finish_reason = "stop"
                            break

                        if chunk.get("id") and round_request_id is None:
                            round_request_id = str(chunk["id"])

                        new_usage = chunk.get("usage")
                        if isinstance(new_usage, dict):
                            round_usage_data = new_usage

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta", {})
                        if choice.get("native_finish_reason"):
                            native_finish_reason = str(choice["native_finish_reason"])

                        tool_calls = delta.get("tool_calls")
                        if isinstance(tool_calls, list):
                            tool_call_chunks.extend(tool_calls)

                        reasoning_delta = delta.get("reasoning_content") or delta.get("reasoning")
                        if preserve_reasoning_content and reasoning_delta:
                            round_reasoning_content += str(reasoning_delta)

                        if choice.get("finish_reason") == "tool_calls":
                            if thinking_started:
                                yield "\n[!THINK]\n"
                                thinking_started = False
                            finish_reason = "tool_calls"
                            break

                        if delta.get("content"):
                            clean_content += str(delta["content"])

                        content, thinking_started = extract_reasoning_text_delta(
                            delta,
                            thinking_started=thinking_started,
                        )
                        if content:
                            full_response += content
                            yield content

                    span.set_data("response_length", len(full_response))

            if round_usage_data and not req.is_title_generation:
                request_index += 1
                usage_data = append_usage_request_breakdown(
                    usage_data,
                    build_usage_request_breakdown(
                        usage_data=round_usage_data,
                        index=request_index,
                        model=req.model,
                        finish_reason=finish_reason,
                        native_finish_reason=native_finish_reason,
                        request_id=round_request_id,
                        tool_names=(
                            extract_tool_names(_merge_tool_call_chunks(tool_call_chunks))
                            if finish_reason == "tool_calls"
                            else []
                        ),
                    ),
                )

            if finish_reason == "tool_calls":
                continuation = await _process_tool_calls_and_continue(
                    tool_call_chunks,
                    messages,
                    req,
                    redis_manager,
                    assistant_content=clean_content if clean_content else None,
                    reasoning_content=(
                        round_reasoning_content if preserve_reasoning_content else None
                    ),
                    require_reasoning_content=preserve_reasoning_content,
                )
                messages = continuation.messages
                req = continuation.req

                for feedback in continuation.feedback_strings:
                    yield feedback

                if continuation.pending_tool_call_id and final_data_container is not None:
                    final_data_container["pending_tool_call_id"] = continuation.pending_tool_call_id

                if continuation.should_continue:
                    full_response = ""
                    clean_content = ""
                    continue
                if continuation.awaiting_user_input:
                    break
                break

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
        logger.info("Stream for node %s was cancelled by the connection manager.", req.node_id)
        raise
    except ConnectError as exc:
        logger.error("Network connection error to %s: %s", provider_label, exc)
        yield (
            "[ERROR]Connection Error: Could not connect to the API. "
            "Please check your network.[!ERROR]"
        )
    except (TimeoutException, AsyncTimeoutError) as exc:
        logger.error("Request to %s timed out: %s", provider_label, exc)
        yield "[ERROR]Timeout: The request to the AI model took too long to respond.[!ERROR]"
    except HTTPStatusError as exc:
        logger.error(
            "HTTP error from %s: %s - %s",
            provider_label,
            exc.response.status_code,
            exc.response.text,
        )
        yield (
            "[ERROR]HTTP Error: Received an invalid response from the server "
            f"(Status: {exc.response.status_code}).[!ERROR]"
        )
    except Exception as exc:
        logger.error(
            "Unexpected error during %s streaming: %s",
            provider_label,
            exc,
            exc_info=True,
        )
        yield "[ERROR]An unexpected server error occurred. Please try again later.[!ERROR]"
