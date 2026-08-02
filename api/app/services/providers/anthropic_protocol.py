import json
import uuid
from enum import Enum
from typing import Any
from urllib.parse import unquote_to_bytes

from services.providers.common import normalize_role_value


def build_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def flush_tool_results() -> None:
        nonlocal pending_tool_results
        if pending_tool_results:
            anthropic_messages.append({"role": "user", "content": pending_tool_results})
            pending_tool_results = []

    for message in messages:
        role = normalize_role_value(message.get("role"))
        if role not in {"system", "user", "assistant", "tool"}:
            continue

        if role == "system":
            system_parts.extend(
                block["text"] for block in _build_anthropic_text_content(message.get("content"))
            )
            continue

        if role == "tool":
            tool_call_id = str(message.get("tool_call_id") or "").strip()
            content = str(message.get("content") or "").strip()
            if tool_call_id and content:
                pending_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": content,
                    }
                )
            continue

        if role == "user":
            content_blocks = _build_anthropic_user_content(message.get("content"))
            if pending_tool_results or content_blocks:
                anthropic_messages.append(
                    {"role": "user", "content": [*pending_tool_results, *content_blocks]}
                )
                pending_tool_results = []
            continue

        flush_tool_results()

        assistant_blocks = _build_anthropic_text_content(
            message.get("content"),
            strip_text=False,
        )

        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function_payload = tool_call.get("function")
                if not isinstance(function_payload, dict):
                    continue
                name = str(function_payload.get("name") or "").strip()
                if not name:
                    continue
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": str(tool_call.get("id") or f"call_{uuid.uuid4().hex}"),
                        "name": name,
                        "input": _deserialize_anthropic_tool_input(
                            function_payload.get("arguments")
                        ),
                    }
                )

        if assistant_blocks:
            anthropic_messages.append({"role": "assistant", "content": assistant_blocks})

    flush_tool_results()

    return "\n\n".join(system_parts) or None, anthropic_messages


def _build_anthropic_user_content(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        text = str(content or "").strip()
        return [{"type": "text", "text": text}] if text else []

    blocks: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = _normalize_content_part_type(part.get("type"))
        if part_type in {"text", "input_text"}:
            text = str(part.get("text") or "").strip()
            if text:
                blocks.append({"type": "text", "text": text})
            continue
        if part_type not in {"image_url", "input_image"}:
            continue
        image_value = part.get("image_url")
        if isinstance(image_value, dict):
            image_value = image_value.get("url")
        data_uri = str(image_value or "")
        if not data_uri.startswith("data:image/") or ";base64," not in data_uri:
            continue
        header, encoded = data_uri.split(",", 1)
        media_type = header[5:].split(";", 1)[0]
        if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
            continue
        try:
            normalized_data = unquote_to_bytes(encoded).decode("ascii")
        except (UnicodeDecodeError, ValueError):
            continue
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": normalized_data,
                },
            }
        )
    return blocks


def _build_anthropic_text_content(
    content: Any,
    *,
    strip_text: bool = True,
) -> list[dict[str, str]]:
    if not isinstance(content, list):
        raw_text = str(content or "")
        text = raw_text.strip() if strip_text else raw_text
        return [{"type": "text", "text": text}] if raw_text.strip() else []

    blocks: list[dict[str, str]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if _normalize_content_part_type(part.get("type")) not in {"text", "input_text"}:
            continue
        raw_text = str(part.get("text") or "")
        text = raw_text.strip() if strip_text else raw_text
        if raw_text.strip():
            blocks.append({"type": "text", "text": text})
    return blocks


def _normalize_content_part_type(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value or "").strip()
    return str(value or "").strip()


def anthropic_tool_calls_to_openai(
    tool_calls_by_index: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_tool_calls: list[dict[str, Any]] = []
    for index in sorted(tool_calls_by_index):
        tool_call = tool_calls_by_index[index]
        arguments = str(tool_call.get("function", {}).get("arguments") or "").strip()
        if arguments:
            try:
                if arguments.startswith("{") and arguments.endswith("}"):
                    arguments = json.dumps(json.loads(arguments), separators=(",", ":"))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        normalized_tool_calls.append(
            {
                "id": str(tool_call.get("id") or f"call_fallback_{uuid.uuid4().hex}"),
                "type": "function",
                "function": {
                    "name": str(tool_call.get("function", {}).get("name") or "").strip(),
                    "arguments": arguments,
                },
            }
        )
    return normalized_tool_calls


def serialize_anthropic_tool_input(input_payload: Any) -> str:
    if input_payload is None:
        return ""
    if isinstance(input_payload, dict) and not input_payload:
        return ""
    try:
        return json.dumps(input_payload, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""


def _deserialize_anthropic_tool_input(input_payload: Any) -> Any:
    if not isinstance(input_payload, str):
        return input_payload if input_payload is not None else {}
    if not input_payload.strip():
        return {}
    try:
        return json.loads(input_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
