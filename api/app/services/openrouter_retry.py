"""Error normalization and bounded retry policy for OpenRouter inference requests."""

import asyncio
import json
import logging
import math
import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

logger = logging.getLogger("uvicorn.error")
RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
TRANSPORT_ERRORS = (
    httpx.NetworkError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    asyncio.TimeoutError,
)


class OpenRouterError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        retryable: bool | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.metadata = metadata or {}
        self.request_id = request_id
        self.retry_after = retry_after
        self.retryable = status_code in RETRYABLE_STATUSES if retryable is None else retryable


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


def normalize_openrouter_error(
    payload: object,
    *,
    status_code: int | None = None,
    headers: Mapping[str, str] | None = None,
    request_id: str | None = None,
) -> OpenRouterError:
    headers = headers or {}
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            pass
    envelope = payload if isinstance(payload, dict) else {}
    error = envelope.get("error", {})
    if not isinstance(error, dict):
        error = {}
    metadata = error.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    code = error.get("code")
    # A real HTTP failure takes precedence over untrusted upstream metadata.
    if status_code is None or status_code == 200:
        try:
            status_code = int(code) if isinstance(code, (str, int)) else None
        except (ValueError, TypeError, OverflowError):
            status_code = None
    message = error.get("message") or (
        payload if isinstance(payload, str) and payload else "Unknown OpenRouter error"
    )
    raw = metadata.get("raw")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            # Preserve provider details for the terminal error, never for classification.
            message = raw or message
    if isinstance(raw, dict) and isinstance(raw.get("error"), dict):
        message = raw["error"].get("message") or message
    retry_after = parse_retry_after(headers.get("retry-after"))
    retryable = status_code in RETRYABLE_STATUSES
    # Only this documented temporary budget condition is a retryable 402.
    if status_code == 402:
        retryable = (
            metadata.get("limit_source") == "openrouter_in_flight_budget"
            and retry_after is not None
        )
    return OpenRouterError(
        str(message),
        status_code=status_code,
        metadata=metadata,
        request_id=request_id or envelope.get("id") or headers.get("x-generation-id"),
        retry_after=retry_after,
        retryable=retryable,
    )


@dataclass(frozen=True)
class RetryStatus:
    attempt: int
    max_attempts: int
    delay_seconds: float

    def payload(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "delay_seconds": self.delay_seconds,
            "message": (
                f"Provider busy. Retrying in {math.ceil(self.delay_seconds)} seconds "
                f"— attempt {self.attempt} of {self.max_attempts}."
            ),
        }


RetryCallback = Callable[[RetryStatus | None], Awaitable[None]]


@dataclass
class RetryBudget:
    max_attempts: int = 4
    max_wait_seconds: float = 90.0
    waited_seconds: float = 0.0

    def delay(self, error: OpenRouterError, attempt: int) -> float | None:
        if not error.retryable or attempt >= self.max_attempts:
            return None
        delay = max(
            random.uniform(0, min(20.0, 2.0 * 2 ** (attempt - 1))),
            error.retry_after or 0.0,
        )
        if self.waited_seconds + delay > self.max_wait_seconds:
            return None
        self.waited_seconds += delay
        return delay


async def wait_for_retry(
    error: OpenRouterError,
    attempt: int,
    budget: RetryBudget,
    on_retry: RetryCallback | None,
) -> None:
    delay = budget.delay(error, attempt)
    if delay is None:
        raise error
    logger.info(
        "Retrying OpenRouter request: status=%s request_id=%s attempt=%s/%s delay=%.2fs",
        error.status_code,
        error.request_id,
        attempt + 1,
        budget.max_attempts,
        delay,
    )
    if on_retry:
        await on_retry(RetryStatus(attempt + 1, budget.max_attempts, delay))
    try:
        await asyncio.sleep(delay)
    finally:
        if on_retry:
            await on_retry(None)
