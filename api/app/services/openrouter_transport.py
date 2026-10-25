"""OpenRouter HTTP/SSE attempts. Retries never cross a tool execution boundary."""

import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import httpx
from services.openrouter_retry import (
    TRANSPORT_ERRORS,
    OpenRouterError,
    RetryBudget,
    RetryCallback,
    normalize_openrouter_error,
    wait_for_retry,
)


async def _sse_data(response: httpx.Response) -> AsyncIterator[str]:
    """Let httpx decode UTF-8 incrementally; support SSE comments and multiline data."""
    data: list[str] = []
    async for line in response.aiter_lines():
        if not line:
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            value = line[5:]
            data.append(value[1:] if value.startswith(" ") else value)
    if data:
        yield "\n".join(data)


def _has_output(chunk: dict[str, Any]) -> bool:
    for choice in chunk.get("choices") or []:
        if (choice.get("message") or {}).get("annotations"):
            return True
        delta = choice.get("delta") or {}
        if any(
            delta.get(key)
            for key in ("content", "reasoning", "reasoning_details", "tool_calls", "annotations")
        ):
            return True
    return False


async def stream_openrouter_data(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    on_retry: RetryCallback | None = None,
) -> AsyncGenerator[str, None]:
    budget = RetryBudget()
    for attempt in range(1, budget.max_attempts + 1):
        committed = False
        finished = False
        buffered: list[str] = []
        request_id = None
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                request_id = response.headers.get("x-generation-id")
                if response.status_code != 200:
                    raise normalize_openrouter_error(
                        await response.aread(),
                        status_code=response.status_code,
                        headers=response.headers,
                        request_id=request_id,
                    )
                if "application/json" in response.headers.get("content-type", ""):
                    raise normalize_openrouter_error(
                        await response.aread(), headers=response.headers, request_id=request_id
                    )
                async for data in _sse_data(response):
                    if data == "[DONE]":
                        for pending in buffered:
                            yield pending
                        yield data
                        return
                    try:
                        chunk = json.loads(data)
                    except ValueError as exc:
                        raise OpenRouterError("OpenRouter returned malformed stream data.") from exc
                    if not isinstance(chunk, dict):
                        raise OpenRouterError("OpenRouter returned malformed stream data.")
                    request_id = chunk.get("id") or request_id
                    if chunk.get("error") is not None:
                        raise normalize_openrouter_error(
                            chunk, headers=response.headers, request_id=request_id
                        )
                    choices = chunk.get("choices") or []
                    if any(choice.get("finish_reason") == "error" for choice in choices):
                        raise OpenRouterError(
                            "OpenRouter stream failed without error details.",
                            request_id=request_id,
                        )
                    finished = finished or any(choice.get("finish_reason") for choice in choices)
                    committed = committed or _has_output(chunk)
                    if committed:
                        for pending in buffered:
                            yield pending
                        buffered.clear()
                        yield data
                    else:
                        buffered.append(data)
                if finished:
                    for pending in buffered:
                        yield pending
                    yield "[DONE]"
                    return
                raise OpenRouterError(
                    "OpenRouter connection ended before the response completed.",
                    status_code=502,
                    request_id=request_id,
                )
        except TRANSPORT_ERRORS as exc:
            error = OpenRouterError(
                "OpenRouter connection failed or timed out.",
                request_id=request_id,
                retryable=True,
            )
            if committed:
                raise error from exc
        except OpenRouterError as exc:
            if committed:
                raise
            error = exc
        # The response context has closed before we notify or sleep.
        await wait_for_retry(error, attempt, budget, on_retry)


async def post_openrouter_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    budget = RetryBudget()
    for attempt in range(1, budget.max_attempts + 1):
        try:
            response = await client.post(url, headers=headers, json=payload)
            try:
                if response.status_code != 200:
                    raise normalize_openrouter_error(
                        response.content,
                        status_code=response.status_code,
                        headers=response.headers,
                    )
                data = response.json()
                if not isinstance(data, dict):
                    raise OpenRouterError("OpenRouter returned malformed response data.")
                if "error" in data:
                    raise normalize_openrouter_error(data, headers=response.headers)
                return data
            finally:
                await response.aclose()
        except TRANSPORT_ERRORS:
            error = OpenRouterError("OpenRouter connection failed or timed out.", retryable=True)
        except OpenRouterError as exc:
            error = exc
        await wait_for_retry(error, attempt, budget, None)
    raise AssertionError("Retry budget exhausted without raising")
