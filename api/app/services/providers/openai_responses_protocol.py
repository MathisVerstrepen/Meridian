import asyncio
import json
import logging
from asyncio import TimeoutError as AsyncTimeoutError
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, TimeoutException
from services.openrouter import _process_tool_calls_and_continue
from services.providers.common import extract_reasoning_text_delta
from services.usage_data import (
    append_usage_request_breakdown,
    build_usage_request_breakdown,
    extract_tool_names,
    finalize_usage_data,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


def build_openai_responses_payload(chat_payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a sanitized Chat Completions payload to a stateless Responses payload."""
    input_items: list[dict[str, Any]] = []
    instructions: str | None = None

    messages = chat_payload.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "")
            if role == "system" and instructions is None:
                text = _string_content(message.get("content"))
                instructions = text or None
                continue
            if role in {"user", "assistant"}:
                text = _string_content(message.get("content"))
                if text:
                    content_type = "input_text" if role == "user" else "output_text"
                    input_items.append(
                        {
                            "type": "message",
                            "role": role,
                            "content": [{"type": content_type, "text": text}],
                        }
                    )
                if role == "assistant":
                    input_items.extend(_convert_chat_tool_calls(message.get("tool_calls")))
                continue
            if role == "tool":
                call_id = str(message.get("tool_call_id") or "").strip()
                output = _string_content(message.get("content"))
                if call_id and output:
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": output,
                        }
                    )

    payload: dict[str, Any] = {
        "model": chat_payload.get("model"),
        "input": input_items,
        "stream": bool(chat_payload.get("stream")),
        "store": False,
    }
    if instructions:
        payload["instructions"] = instructions
    for field_name in ("temperature", "top_p"):
        if field_name in chat_payload:
            payload[field_name] = chat_payload[field_name]
    if "max_tokens" in chat_payload:
        payload["max_output_tokens"] = chat_payload["max_tokens"]

    tools = _flatten_chat_tools(chat_payload.get("tools"))
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return {key: value for key, value in payload.items() if value is not None}


def _string_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") in {
            "text",
            "input_text",
            "output_text",
            "refusal",
        }:
            value_key = "refusal" if part.get("type") == "refusal" else "text"
            text = str(part.get(value_key) or "")
            if text:
                parts.append(text)
    return "".join(parts)


def _json_arguments(arguments: Any) -> str:
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments or {}, separators=(",", ":"))


def _convert_chat_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    if not isinstance(tool_calls, list):
        return converted
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function")
        if not isinstance(function, dict):
            continue
        call_id = str(tool_call.get("id") or "").strip()
        name = str(function.get("name") or "").strip()
        if call_id and name:
            converted.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": _json_arguments(function.get("arguments")),
                }
            )
    return converted


def _flatten_chat_tools(tools: Any) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    if not isinstance(tools, list):
        return flattened
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            continue
        function = tool.get("function")
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        flattened.append(
            {
                "type": "function",
                "name": name,
                "description": str(function.get("description") or ""),
                "parameters": function.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return flattened


def extract_openai_responses_text(output: Any) -> str:
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        text = _string_content(item.get("content"))
        if text:
            parts.append(text)
    return "".join(parts)


def extract_openai_responses_function_calls(output: Any) -> list[dict[str, Any]]:
    if not isinstance(output, list):
        return []
    calls: list[dict[str, Any]] = []
    for index, item in enumerate(output):
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        call_id = str(item.get("call_id") or item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not call_id or not name:
            continue
        calls.append(
            {
                "index": index,
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": _json_arguments(item.get("arguments")),
                },
            }
        )
    return calls


def normalize_openai_responses_usage(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0) or prompt_tokens + completion_tokens
    input_details = usage.get("input_tokens_details")
    output_details = usage.get("output_tokens_details")
    cached_tokens = (
        int(input_details.get("cached_tokens", 0) or 0) if isinstance(input_details, dict) else 0
    )
    reasoning_tokens = (
        int(output_details.get("reasoning_tokens", 0) or 0)
        if isinstance(output_details, dict)
        else 0
    )
    if not any((prompt_tokens, completion_tokens, total_tokens, cached_tokens, reasoning_tokens)):
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_tokens_details": {"cached_tokens": cached_tokens},
        "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
        "cost_details": {},
    }


async def iter_openai_responses_sse_events(
    response: httpx.Response,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    event_type = ""
    data_lines: list[str] = []
    buffer = ""

    def emit_event() -> tuple[str, dict[str, Any]] | None:
        nonlocal event_type, data_lines
        data = "\n".join(data_lines).strip()
        current_event_type = event_type
        event_type = ""
        data_lines = []
        if not data or data == "[DONE]":
            return None
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return current_event_type or str(parsed.get("type") or ""), parsed

    async for byte_chunk in response.aiter_bytes():
        buffer += byte_chunk.decode("utf-8", errors="ignore")
        lines = buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            buffer = lines.pop()
        else:
            buffer = ""
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if emitted := emit_event():
                    yield emitted
            elif line.startswith("event:"):
                event_type = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())

    if buffer:
        line = buffer.strip()
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
    if emitted := emit_event():
        yield emitted


@dataclass
class _ResponsesRoundState:
    streamed_text: str = ""
    clean_text: str = ""
    thinking_started: bool = False
    reasoning_text: str = ""
    function_calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    argument_deltas: dict[str, str] = field(default_factory=dict)
    usage: dict[str, Any] | None = None
    request_id: str | None = None
    status: str | None = None
    terminal: bool = False


def _event_response(event_data: dict[str, Any]) -> dict[str, Any]:
    response = event_data.get("response")
    return response if isinstance(response, dict) else {}


def _event_public_error(event_data: dict[str, Any]) -> str | None:
    error = event_data.get("error")
    error_message = error.get("message") if isinstance(error, dict) else None
    if isinstance(error_message, str):
        return error_message
    response_error = _event_response(event_data).get("error")
    response_error_message = (
        response_error.get("message") if isinstance(response_error, dict) else None
    )
    if isinstance(response_error_message, str):
        return response_error_message
    return None


def _record_function_call(state: _ResponsesRoundState, item: Any) -> None:
    if not isinstance(item, dict) or item.get("type") != "function_call":
        return
    call_id = str(item.get("call_id") or item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    if not call_id or not name:
        return
    arguments = item.get("arguments")
    if arguments in (None, ""):
        arguments = state.argument_deltas.get(call_id) or state.argument_deltas.get(
            str(item.get("id") or "")
        )
    state.function_calls[call_id] = {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": _json_arguments(arguments)},
    }


def _completed_output(event_data: dict[str, Any]) -> list[Any]:
    response = _event_response(event_data)
    output = response.get("output")
    return output if isinstance(output, list) else []


async def stream_openai_responses_response(
    req: Any,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    *,
    provider_label: str,
    error_parser: Callable[[bytes], str],
    error_sanitizer: Callable[[str], str],
    final_data_container: Optional[dict[str, Any]] = None,
    span_description: str,
    rejected_response_observer: (
        Callable[[Any, httpx.Response, dict[str, Any], bytes], None] | None
    ) = None,
    terminal_event_observer: Callable[[str, dict[str, Any], dict[str, int]], None] | None = None,
) -> AsyncIterator[str]:
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    messages = req.messages.copy()
    usage_data: dict[str, Any] | None = None
    request_index = 0

    def observe_terminal_event(
        event_type: str,
        event_data: dict[str, Any],
        event_counts: dict[str, int],
    ) -> None:
        if terminal_event_observer is None:
            return
        try:
            terminal_event_observer(event_type, event_data, event_counts)
        except Exception:
            logger.warning(
                "%s terminal-event observer failed.",
                provider_label,
                exc_info=True,
            )

    try:
        while True:
            state = _ResponsesRoundState()
            event_counts: dict[str, int] = {}
            payload = req.get_payload()
            async with client.stream(
                "POST", req.api_url, headers=req.headers, json=payload
            ) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    if rejected_response_observer is not None:
                        try:
                            rejected_response_observer(req, response, payload, error_content)
                        except Exception:
                            logger.warning(
                                "%s rejected-response observer failed.",
                                provider_label,
                                exc_info=True,
                            )
                    yield (
                        f"[ERROR]Stream Error: Failed to get response from {provider_label} "
                        f"(Status: {response.status_code}). \n"
                        f"{error_parser(error_content)}[!ERROR]"
                    )
                    return

                with sentry_sdk.start_span(op="ai.streaming", description=span_description) as span:
                    span.set_tag("chat.model", req.model)
                    async for event_type, event_data in iter_openai_responses_sse_events(response):
                        event_counts[event_type] = event_counts.get(event_type, 0) + 1
                        if event_type in {"error", "response.failed", "response.incomplete"}:
                            observe_terminal_event(event_type, event_data, event_counts)
                            public_error = _event_public_error(event_data)
                            message = (
                                error_sanitizer(public_error)
                                if public_error
                                else "OpenCode Go returned an unknown API error."
                            )
                            yield f"[ERROR]{message}[!ERROR]"
                            return

                        if event_type in {
                            "response.output_text.delta",
                            "response.refusal.delta",
                        }:
                            delta = str(event_data.get("delta") or "")
                            if delta:
                                state.clean_text += delta
                                state.streamed_text += delta
                                visible_text, state.thinking_started = extract_reasoning_text_delta(
                                    {"content": delta},
                                    thinking_started=state.thinking_started,
                                )
                                yield visible_text
                            continue

                        if event_type in {
                            "response.reasoning_summary_text.delta",
                            "response.reasoning_summary.delta",
                            "response.reasoning_text.delta",
                        }:
                            delta = str(event_data.get("delta") or "")
                            if delta:
                                if not state.thinking_started:
                                    yield "[THINK]\n"
                                    state.thinking_started = True
                                state.reasoning_text += delta
                                yield delta
                            continue

                        if event_type == "response.function_call_arguments.delta":
                            key = str(
                                event_data.get("call_id")
                                or event_data.get("item_id")
                                or event_data.get("output_index")
                                or ""
                            )
                            if key:
                                state.argument_deltas[key] = state.argument_deltas.get(
                                    key, ""
                                ) + str(event_data.get("delta") or "")
                            continue

                        if event_type == "response.output_item.done":
                            _record_function_call(state, event_data.get("item"))
                            continue

                        if event_type != "response.completed":
                            continue

                        response_payload = _event_response(event_data)
                        state.request_id = str(response_payload.get("id") or "") or None
                        state.status = str(response_payload.get("status") or "completed")
                        if state.status in {"failed", "incomplete"}:
                            observe_terminal_event(event_type, event_data, event_counts)
                            public_error = _event_public_error(event_data)
                            message = (
                                error_sanitizer(public_error)
                                if public_error
                                else "OpenCode Go returned an incomplete response."
                            )
                            yield f"[ERROR]{message}[!ERROR]"
                            return
                        state.usage = normalize_openai_responses_usage(
                            response_payload.get("usage") or event_data.get("usage")
                        )
                        output = _completed_output(event_data)
                        for item in output:
                            _record_function_call(state, item)
                        completed_text = extract_openai_responses_text(output)
                        if completed_text and not state.streamed_text:
                            state.clean_text += completed_text
                            state.streamed_text = completed_text
                            visible_text, state.thinking_started = extract_reasoning_text_delta(
                                {"content": completed_text},
                                thinking_started=state.thinking_started,
                            )
                            yield visible_text
                        elif completed_text.startswith(state.streamed_text):
                            suffix = completed_text[len(state.streamed_text) :]
                            if suffix:
                                state.clean_text += suffix
                                state.streamed_text += suffix
                                visible_text, state.thinking_started = extract_reasoning_text_delta(
                                    {"content": suffix},
                                    thinking_started=state.thinking_started,
                                )
                                yield visible_text
                        state.terminal = True
                        break

                    if state.thinking_started:
                        yield "\n[!THINK]\n"
                        state.thinking_started = False
                    span.set_data("response_length", len(state.streamed_text))

            tool_calls = list(state.function_calls.values())
            finish_reason = "tool_calls" if tool_calls else "stop"
            if state.usage and not req.is_title_generation:
                request_index += 1
                usage_data = append_usage_request_breakdown(
                    usage_data,
                    build_usage_request_breakdown(
                        usage_data=state.usage,
                        index=request_index,
                        model=req.model,
                        finish_reason=finish_reason,
                        native_finish_reason=state.status,
                        request_id=state.request_id,
                        tool_names=extract_tool_names(tool_calls) if tool_calls else [],
                    ),
                )

            if tool_calls:
                continuation = await _process_tool_calls_and_continue(
                    tool_calls,
                    messages,
                    req,
                    redis_manager,
                    assistant_content=state.clean_text or None,
                )
                messages = continuation.messages
                req = continuation.req
                req.messages = messages
                for feedback in continuation.feedback_strings:
                    yield feedback
                if continuation.pending_tool_call_id and final_data_container is not None:
                    final_data_container["pending_tool_call_id"] = continuation.pending_tool_call_id
                if continuation.should_continue:
                    continue
                break

            if not state.terminal:
                observe_terminal_event("missing_terminal", {}, event_counts)
                yield "[ERROR]OpenCode Go returned an incomplete response.[!ERROR]"
            break

        finalized_usage = finalize_usage_data(usage_data)
        if finalized_usage and not req.is_title_generation and final_data_container is not None:
            final_data_container["usage_data"] = finalized_usage
        if finalized_usage and req.graph_id and req.node_id and not req.is_title_generation:
            await update_node_usage_data(
                pg_engine=pg_engine,
                graph_id=req.graph_id,
                node_id=req.node_id,
                usage_data=finalized_usage,
                node_type=req.node_type,
                model_id=req.model_id,
            )
    except asyncio.CancelledError:
        logger.info("Stream for node %s was cancelled by connection manager.", req.node_id)
        raise
    except ConnectError as exc:
        logger.error("Network connection error to %s: %s", provider_label, exc)
        yield "[ERROR]Connection Error: Could not connect to the API.[!ERROR]"
    except (TimeoutException, AsyncTimeoutError) as exc:
        logger.error("Request to %s timed out: %s", provider_label, exc)
        yield "[ERROR]Timeout: The request to the AI model took too long to respond.[!ERROR]"
    except Exception as exc:
        logger.error(
            "Unexpected error during %s Responses streaming: %s",
            provider_label,
            exc,
            exc_info=True,
        )
        yield "[ERROR]An unexpected server error occurred. Please try again later.[!ERROR]"
