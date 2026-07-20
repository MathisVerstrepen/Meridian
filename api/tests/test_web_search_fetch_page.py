import asyncio
import logging
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.web import web_search
from services.web.fetch_errors import (
    LinkExtractionError,
    LinkExtractionFailureReason,
    failure_user_message,
)


class FakeSpan:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.status: str | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def set_data(self, key: str, value: object) -> None:
        self.data[key] = value

    def set_status(self, status: str) -> None:
        self.status = status


@pytest.fixture
def boundary_fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[list[FakeSpan], list[str]]:
    spans: list[FakeSpan] = []
    sentry_messages: list[str] = []

    def start_span(**kwargs) -> FakeSpan:
        span = FakeSpan()
        spans.append(span)
        return span

    async def allow_usage(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(web_search.sentry_sdk, "start_span", start_span)
    monkeypatch.setattr(
        web_search.sentry_sdk,
        "capture_message",
        lambda message, **kwargs: sentry_messages.append(message),
    )
    monkeypatch.setattr(web_search, "check_and_increment_query_usage", allow_usage)
    return spans, sentry_messages


@pytest.mark.parametrize(
    ("reason", "status_code", "expected"),
    [
        (
            LinkExtractionFailureReason.HTTP_REJECTED,
            403,
            "The page rejected the request (HTTP 403).",
        ),
        (
            LinkExtractionFailureReason.HTTP_REJECTED,
            None,
            "The page rejected the request.",
        ),
        (
            LinkExtractionFailureReason.CONNECTIVITY_EXHAUSTED,
            None,
            "The page could not be reached after temporary connection failures.",
        ),
        (
            LinkExtractionFailureReason.CHALLENGE_UNRESOLVED,
            None,
            "The page presented a browser challenge that could not be resolved.",
        ),
        (
            LinkExtractionFailureReason.BROWSER_FAILED,
            None,
            "The browser fallback could not initialize or load the page.",
        ),
        (
            LinkExtractionFailureReason.UNUSABLE_CONTENT,
            None,
            "The page was fetched, but no usable content could be extracted.",
        ),
        (
            LinkExtractionFailureReason.FETCH_FAILED,
            None,
            "The page could not be fetched or processed.",
        ),
    ],
)
def test_failure_user_message_exact_text(
    reason: LinkExtractionFailureReason,
    status_code: int | None,
    expected: str,
) -> None:
    assert failure_user_message(LinkExtractionError(reason, status_code)) == expected


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429, 500, 599])
def test_http_status_message_exposes_only_valid_decimal_status(status_code: int) -> None:
    error = LinkExtractionError(LinkExtractionFailureReason.HTTP_REJECTED, status_code)

    assert failure_user_message(error) == f"The page rejected the request (HTTP {status_code})."


@pytest.mark.parametrize("status_code", [None, 399, 600, True, "403"])
def test_invalid_http_status_uses_status_free_message(status_code: object) -> None:
    error = LinkExtractionError(
        LinkExtractionFailureReason.HTTP_REJECTED,
        status_code,  # type: ignore[arg-type]
    )

    assert error.status_code is None
    assert failure_user_message(error) == "The page rejected the request."


def test_invalid_failure_reason_normalizes_to_safe_catch_all() -> None:
    error = LinkExtractionError("raw secret reason", 403)  # type: ignore[arg-type]

    assert error.reason is LinkExtractionFailureReason.FETCH_FAILED
    assert failure_user_message(error) == "The page could not be fetched or processed."


@pytest.mark.parametrize(
    ("reason", "status_code", "expected"),
    [
        (
            LinkExtractionFailureReason.HTTP_REJECTED,
            429,
            "The page rejected the request (HTTP 429).",
        ),
        (
            LinkExtractionFailureReason.CONNECTIVITY_EXHAUSTED,
            None,
            "The page could not be reached after temporary connection failures.",
        ),
        (
            LinkExtractionFailureReason.CHALLENGE_UNRESOLVED,
            None,
            "The page presented a browser challenge that could not be resolved.",
        ),
        (
            LinkExtractionFailureReason.BROWSER_FAILED,
            None,
            "The browser fallback could not initialize or load the page.",
        ),
        (
            LinkExtractionFailureReason.UNUSABLE_CONTENT,
            None,
            "The page was fetched, but no usable content could be extracted.",
        ),
        (
            LinkExtractionFailureReason.FETCH_FAILED,
            None,
            "The page could not be fetched or processed.",
        ),
    ],
)
def test_fetch_page_maps_typed_failures_to_exact_safe_errors(
    monkeypatch: pytest.MonkeyPatch,
    boundary_fakes: tuple[list[FakeSpan], list[str]],
    reason: LinkExtractionFailureReason,
    status_code: int | None,
    expected: str,
) -> None:
    async def fail_extraction(url: str) -> str:
        raise LinkExtractionError(reason, status_code) from RuntimeError(
            "raw proxy=password cookie=session body=secret"
        )

    monkeypatch.setattr(web_search, "url_to_markdown", fail_extraction)

    result = asyncio.run(
        web_search.fetch_page(
            "https://user:password@example.com/article?token=query-secret",
            1000,
            object(),
            "user-id",
        )
    )

    spans, sentry_messages = boundary_fakes
    assert result == {"error": expected}
    assert spans[0].data["url"] == "https://example.com/article"
    assert spans[0].data["failure_reason"] == reason.value
    assert sentry_messages == []
    serialized = repr(result) + repr(spans[0].data)
    assert "password" not in serialized
    assert "query-secret" not in serialized
    assert "cookie" not in serialized
    assert "session" not in serialized


def test_fetch_page_preserves_success_and_truncation(
    monkeypatch: pytest.MonkeyPatch,
    boundary_fakes: tuple[list[FakeSpan], list[str]],
) -> None:
    async def successful_extraction(url: str) -> str:
        return "abcdefghij"

    monkeypatch.setattr(web_search, "url_to_markdown", successful_extraction)

    full = asyncio.run(web_search.fetch_page("https://example.com", 20, object(), "user-id"))
    truncated = asyncio.run(web_search.fetch_page("https://example.com", 5, object(), "user-id"))

    assert full == {"markdown_content": "abcdefghij"}
    assert truncated == {"markdown_content": "abcde\n... (content truncated)"}


def test_usage_error_is_unchanged_and_skips_extraction(
    monkeypatch: pytest.MonkeyPatch,
    boundary_fakes: tuple[list[FakeSpan], list[str]],
) -> None:
    extraction_called = False

    async def deny_usage(*args, **kwargs) -> None:
        raise HTTPException(status_code=429, detail="Link extraction limit reached")

    async def extraction(url: str) -> str:
        nonlocal extraction_called
        extraction_called = True
        return "unused"

    monkeypatch.setattr(web_search, "check_and_increment_query_usage", deny_usage)
    monkeypatch.setattr(web_search, "url_to_markdown", extraction)

    result = asyncio.run(web_search.fetch_page("https://example.com", 100, object(), "user-id"))

    assert result == {"error": "Usage Error: Link extraction limit reached"}
    assert extraction_called is False


def test_unexpected_failure_returns_and_reports_only_controlled_data(
    monkeypatch: pytest.MonkeyPatch,
    boundary_fakes: tuple[list[FakeSpan], list[str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    secrets = [
        "proxy.internal.example",
        "proxy-user",
        "proxy-password",
        "cookie-value",
        "query-secret",
        "raw-body-secret",
    ]

    async def unexpected_failure(url: str) -> str:
        raise RuntimeError(" ".join(secrets))

    monkeypatch.setattr(web_search, "url_to_markdown", unexpected_failure)

    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        result = asyncio.run(
            web_search.fetch_page(
                "https://target-user:target-password@example.com/article?token=query-secret",
                100,
                object(),
                "user-id",
            )
        )

    spans, sentry_messages = boundary_fakes
    assert result == {"error": "The page could not be fetched or processed."}
    captured = repr(result) + repr(spans[0].data) + repr(sentry_messages) + caplog.text
    for secret in secrets:
        assert secret not in captured
    assert "target-user" not in captured
    assert "target-password" not in captured
    assert sentry_messages == ["Unexpected link extraction failure"]
