"""Thinking controls and final-text validation for OpenCode Go helper completions."""

import logging

from services.providers.common import strip_model_prefix
from services.providers.opencode_go_catalog import OPENCODE_GO_MODEL_PREFIX

logger = logging.getLogger("uvicorn.error")


class OpenCodeGoEmptyResponseError(ValueError):
    """The provider completed without returning any final text."""


def thinking_payload(
    model: str, is_auxiliary: bool, effort: str | None = None
) -> dict[str, object]:
    # Hiding reasoning does not disable DeepSeek's default thinking mode. Short
    # auxiliary tasks disable it; other requests honor the configured effort.
    key = strip_model_prefix(model, OPENCODE_GO_MODEL_PREFIX)
    if not key.startswith("deepseek-"):
        return {}
    if is_auxiliary or effort == "none":
        return {"thinking": {"type": "disabled"}}
    mapped = {
        "minimal": "low",
        "low": "low",
        "medium": "high",
        "high": "high",
        "xhigh": "high",
        "max": "max",
    }.get(effort or "")
    if mapped:
        return {"thinking": {"type": "enabled"}, "reasoning_effort": mapped}
    return {}


def require_completion_text(content: str, *, model: str, finish_reason: object) -> str:
    if content.strip():
        return content
    safe_reason = (
        finish_reason
        if isinstance(finish_reason, str) and finish_reason in {"length", "stop", "content_filter"}
        else "unknown"
    )
    logger.warning(
        "OpenCode Go returned no final text: model=%s finish_reason=%s", model, safe_reason
    )
    if finish_reason == "length":
        raise OpenCodeGoEmptyResponseError(
            "OpenCode Go reached its token limit before returning final text."
        )
    raise OpenCodeGoEmptyResponseError("OpenCode Go returned an empty response. Try again.")
