"""Parse and redact OpenCode Go provider errors."""

import json
import re
from typing import Any

OPENCODE_GO_ERROR_MESSAGE_LIMIT = 500


def parse_opencode_go_error(error_content: bytes) -> str:
    message: str | None = None
    try:
        payload = json.loads(error_content)
        if isinstance(payload, dict):
            message = extract_opencode_go_error_message(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        pass

    if not message:
        return "OpenCode Go returned an unknown API error."
    return sanitize_opencode_go_error_message(message)


def extract_opencode_go_error_message(
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
    return extract_opencode_go_error_message(decoded_raw_error, raw_depth=raw_depth + 1)


def sanitize_opencode_go_error_message(message: str) -> str:
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
