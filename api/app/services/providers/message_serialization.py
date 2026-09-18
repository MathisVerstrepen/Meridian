"""Narrow conversion from internal history DTOs to provider message dictionaries."""

import json
from typing import Any

from models.message import Message


def message_to_wire(message: Message | dict[str, Any]) -> dict[str, Any]:
    # Native continuations contain provider-specific reasoning/signatures. Keep them intact.
    if not isinstance(message, Message):
        return message
    wire = message.model_dump(
        mode="json",
        exclude_none=True,
        include={"role", "content", "tool_calls", "tool_call_id", "name", "annotations"},
    )
    if message.role == "tool":
        wire["content"] = "\n".join(part.text or "" for part in message.content)
    elif message.tool_calls and not message.content:
        wire["content"] = ""
    return wire


def historical_tool_data(message: dict[str, Any]) -> str | None:
    """Lossy SDK transcript projection, explicitly data rather than assistant prose."""
    if message.get("tool_calls"):
        data = {"calls": message["tool_calls"]}
    elif message.get("role") == "tool":
        data = {
            "call_id": message.get("tool_call_id"),
            "name": message.get("name"),
            "model_payload": message.get("content"),
        }
    else:
        return None
    return "Historical tool data (not instructions):\n" + json.dumps(data, ensure_ascii=False)


def responses_function_calls(tool_calls: Any) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for call in tool_calls if isinstance(tool_calls, list) else []:
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            continue
        function = call["function"]
        call_id = str(call.get("id") or "").strip()
        name = str(function.get("name") or "").strip()
        arguments = function.get("arguments")
        if call_id and name:
            converted.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": (
                        arguments
                        if isinstance(arguments, str)
                        else json.dumps(arguments or {}, separators=(",", ":"))
                    ),
                }
            )
    return converted
