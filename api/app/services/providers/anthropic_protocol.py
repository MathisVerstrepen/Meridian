import json
import uuid
from typing import Any

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
            content = str(message.get("content") or "").strip()
            if content:
                system_parts.append(content)
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

        flush_tool_results()

        if role == "user":
            content = str(message.get("content") or "").strip()
            if content:
                anthropic_messages.append(
                    {"role": "user", "content": [{"type": "text", "text": content}]}
                )
            continue

        assistant_blocks: list[dict[str, Any]] = []
        content = str(message.get("content") or "")
        if content.strip():
            assistant_blocks.append({"type": "text", "text": content})

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
