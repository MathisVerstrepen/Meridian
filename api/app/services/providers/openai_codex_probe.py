"""Probe ChatGPT Codex credentials with current, bounded model fallbacks."""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

# Prefer the efficient model for this tiny probe. Availability varies by plan,
# workspace settings, and rollout; try another only on explicit model rejection.
OPENAI_CODEX_PROBE_MODELS = ("gpt-6-luna", "gpt-6.1-sol", "gpt-6-sol")
CodexEventIterator = Callable[[httpx.Response], AsyncIterator[tuple[str, dict[str, Any]]]]


def format_openai_codex_probe_error(status_code: int, body: str) -> str:
    detail = body[:500].strip()
    suffix = f" ({status_code} {detail})" if detail else f" ({status_code})"
    if status_code == 401:
        message = "OpenAI Codex authentication is invalid or unavailable. Sign in again."
    elif status_code == 403:
        message = "OpenAI Codex access was denied. Check your account and workspace permissions."
    else:
        message = "OpenAI Codex validation failed."
    return message + suffix


def _is_unsupported_probe_model(status_code: int, body: str) -> bool:
    message = body.lower()
    return (
        status_code in (200, 400, 404)
        and "model" in message
        and any(
            marker in message
            for marker in ("not supported", "not available", "not found", "does not exist")
        )
    )


async def _probe_model(
    client: httpx.AsyncClient,
    endpoint: str,
    headers: dict[str, str],
    model: str,
    iter_events: CodexEventIterator,
) -> tuple[int, str] | None:
    payload = {
        "model": model,
        "instructions": "Validate this OpenAI Codex session. Reply with OK.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Reply with OK."}],
            }
        ],
        "store": False,
        "stream": True,
        "include": [],
    }
    async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
        if response.status_code >= 400:
            body = (await response.aread()).decode("utf-8", errors="replace")
            return response.status_code, body
        async for event_type, event_data in iter_events(response):
            response_payload = event_data.get("response")
            nested_error = (
                response_payload.get("error") if isinstance(response_payload, dict) else None
            )
            error_payload = event_data.get("error") or nested_error
            if event_type in {"error", "response.failed", "response.incomplete"} or error_payload:
                return 200, json.dumps(error_payload or event_data, separators=(",", ":"))
            if event_type == "response.completed":
                return None
    return 200, "The validation stream ended without a completed response."


async def probe_openai_codex_session(
    client: httpx.AsyncClient,
    endpoint: str,
    headers: dict[str, str],
    *,
    iter_events: CodexEventIterator,
) -> None:
    for model in OPENAI_CODEX_PROBE_MODELS:
        error = await _probe_model(client, endpoint, headers, model, iter_events)
        if error is None:
            return
        status_code, body = error
        if not _is_unsupported_probe_model(status_code, body):
            raise ValueError(format_openai_codex_probe_error(status_code, body))

    raise ValueError(
        "OpenAI Codex validation failed: none of the validation models is available to this "
        "ChatGPT account. Check model access for your plan and workspace."
    )
