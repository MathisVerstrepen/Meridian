import asyncio

import pytest
from playwright._impl._errors import TargetClosedError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser_service.app import browser_challenge
from browser_service.app.browser_challenge import is_browser_challenge, resolve_browser_challenge
from browser_service.app.models import BrowserFetchError, FailureReason

CHALLENGE = "<html><p id='cmsg'>Please enable JS and disable any ad blocker</p></html>"
CHALLENGE_HEADERS = {"x-cache": "LambdaGeneratedResponse from cloudfront"}
VALID_CONTENT = "<html><body>" + "useful content " * 200 + "</body></html>"


class Response:
    def __init__(self, status: int = 403, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._headers = headers if headers is not None else CHALLENGE_HEADERS

    async def all_headers(self):
        return self._headers


class BlockedPage:
    url = "https://arbitrary.example/article"

    def __init__(self) -> None:
        self.reload_calls = []
        self.wait_calls = 0

    async def content(self):
        return CHALLENGE

    async def wait_for_function(self, expression, **kwargs):
        self.wait_calls += 1
        assert expression == browser_challenge.CHALLENGE_CLEAR_CONDITION
        assert 0 < kwargs["timeout"] <= 5000
        raise PlaywrightTimeoutError("still blocked")

    async def reload(self, **kwargs):
        self.reload_calls.append(kwargs)
        return Response()


@pytest.mark.parametrize("status_code", [401, 403])
@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({}, "Please enable JS and disable any ad blocker"),
        (CHALLENGE_HEADERS, "<p id='cmsg'>Checking</p>"),
        ({"X-Cache": "edge LAMBDAGENERATEDRESPONSE"}, "<style>#cmsg {}</style>"),
    ],
)
def test_browser_challenge_accepts_conservative_evidence_on_both_statuses(
    status_code: int, headers: dict[str, str], body: str
) -> None:
    assert is_browser_challenge(status_code, headers, body)


@pytest.mark.parametrize(
    ("status_code", "headers", "body"),
    [
        (200, {}, "Please enable JS and disable any ad blocker"),
        (401, {}, "<p id='cmsg'>Sign in</p>"),
        (403, {"x-cache": "MISS"}, "#cmsg"),
        (403, CHALLENGE_HEADERS, "Access denied"),
        (401, {}, "Please enable JavaScript to continue"),
        (401, {}, "Sign in to continue"),
        (403, {"server": "Varnish", "retry-after": "0"}, "Forbidden"),
        (403, {"server": "snooserv", "via": "1.1 varnish"}, "Forbidden"),
        (403, {}, "x" * 8192 + "Please enable JS and disable any ad blocker"),
    ],
)
def test_browser_challenge_rejects_false_positives(
    status_code: int, headers: dict[str, str], body: str
) -> None:
    assert not is_browser_challenge(status_code, headers, body)


def test_exact_budget_and_single_bounded_reload() -> None:
    assert browser_challenge.CHALLENGE_BODY_SCAN_LENGTH == 8192
    assert browser_challenge.CHALLENGE_TOTAL_TIMEOUT_SECONDS == 15
    assert browser_challenge.CHALLENGE_OPERATION_TIMEOUT_MS == 5000
    page = BlockedPage()

    async def scenario() -> None:
        with pytest.raises(BrowserFetchError) as captured:
            await resolve_browser_challenge(
                page,
                Response(),
                CHALLENGE,
                page.url,
                CHALLENGE_HEADERS,
                proxy_enabled=True,
            )
        assert captured.value.reason is FailureReason.CHALLENGE_UNRESOLVED

    asyncio.run(scenario())
    assert page.wait_calls == 2
    assert len(page.reload_calls) == 1
    assert page.reload_calls[0]["wait_until"] == "domcontentloaded"
    assert 0 < page.reload_calls[0]["timeout"] <= 5000


def test_cross_host_redirect_is_accepted_after_evidence_clears() -> None:
    class RedirectPage(BlockedPage):
        url = "https://content.example/final"

        async def wait_for_function(self, expression, **kwargs):
            self.wait_calls += 1

        async def content(self):
            return VALID_CONTENT

    page = RedirectPage()
    result = asyncio.run(
        resolve_browser_challenge(
            page,
            Response(status=401),
            CHALLENGE,
            "https://challenge.example/start",
            {},
            proxy_enabled=False,
        )
    )
    assert result == VALID_CONTENT
    assert page.wait_calls == 1
    assert page.reload_calls == []


def test_cleared_but_insufficient_content_is_typed_unusable() -> None:
    class ShortPage(BlockedPage):
        async def wait_for_function(self, expression, **kwargs):
            self.wait_calls += 1

        async def content(self):
            return "<html>short</html>"

        async def reload(self, **kwargs):
            self.reload_calls.append(kwargs)
            return Response(status=200, headers={})

    page = ShortPage()

    async def scenario() -> None:
        with pytest.raises(BrowserFetchError) as captured:
            await resolve_browser_challenge(
                page,
                Response(),
                CHALLENGE,
                page.url,
                CHALLENGE_HEADERS,
                proxy_enabled=False,
            )
        assert captured.value.reason is FailureReason.UNUSABLE_CONTENT

    asyncio.run(scenario())
    assert page.wait_calls == 1
    assert len(page.reload_calls) == 1


def test_timeout_diagnostics_use_only_state_captured_within_deadline(monkeypatch) -> None:
    page = BlockedPage()

    async def expire(*args, **kwargs):
        raise TimeoutError

    async def forbidden_content():
        raise AssertionError("post-deadline page read")

    monkeypatch.setattr(browser_challenge, "_wait_for_clear", expire)
    page.content = forbidden_content

    async def scenario() -> None:
        with pytest.raises(BrowserFetchError) as captured:
            await resolve_browser_challenge(
                page,
                Response(),
                CHALLENGE,
                page.url,
                CHALLENGE_HEADERS,
                proxy_enabled=True,
            )
        assert captured.value.reason is FailureReason.CHALLENGE_UNRESOLVED

    asyncio.run(scenario())


def test_resolver_preserves_target_closed_error() -> None:
    class ClosedDuringWaitPage(BlockedPage):
        async def wait_for_function(self, expression, **kwargs):
            raise TargetClosedError("closed")

    async def scenario() -> None:
        with pytest.raises(TargetClosedError):
            await resolve_browser_challenge(
                ClosedDuringWaitPage(),
                Response(),
                CHALLENGE,
                "https://example.com/challenge",
                CHALLENGE_HEADERS,
                proxy_enabled=False,
            )

    asyncio.run(scenario())


def test_diagnostic_helpers_preserve_target_closed_errors() -> None:
    class ClosedPage:
        async def content(self):
            raise TargetClosedError("closed")

    class ClosedResponse:
        async def all_headers(self):
            raise TargetClosedError("closed")

    class BrokenPage:
        async def content(self):
            raise RuntimeError("ordinary diagnostic failure")

    class BrokenResponse:
        async def all_headers(self):
            raise RuntimeError("ordinary diagnostic failure")

    async def scenario() -> None:
        with pytest.raises(TargetClosedError):
            await browser_challenge.safe_page_content(ClosedPage())
        with pytest.raises(TargetClosedError):
            await browser_challenge.response_headers(ClosedResponse())
        assert await browser_challenge.safe_page_content(BrokenPage()) == ""
        assert await browser_challenge.response_headers(BrokenResponse()) == {}

    asyncio.run(scenario())
