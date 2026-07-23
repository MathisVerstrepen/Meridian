import asyncio
import sys
from pathlib import Path

import pytest
from curl_cffi.requests.exceptions import ConnectionError, ProxyError, Timeout

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.web import http_fetch


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


class FakeResponse:
    def __init__(
        self,
        text: str,
        status_code: int = 200,
        url: str = "https://example.com/article",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


@pytest.fixture(autouse=True)
def fake_sentry_span(monkeypatch: pytest.MonkeyPatch):
    spans: list[FakeSpan] = []

    def start_span(**kwargs):
        span = FakeSpan()
        spans.append(span)
        return span

    monkeypatch.setattr(http_fetch.sentry_sdk, "start_span", start_span)
    return spans


def test_fetch_uses_coherent_curl_fingerprint(fake_sentry_span: list[FakeSpan]) -> None:
    session = FakeSession(FakeResponse("x" * http_fetch.MIN_HTML_LENGTH))

    result = asyncio.run(
        http_fetch.fetch_http_once(
            session,
            "https://user:password@example.com/article?token=secret",
            proxy="http://proxy-user:proxy-password@proxy.example:8080",
        )
    )

    assert result == "x" * http_fetch.MIN_HTML_LENGTH
    _, kwargs = session.calls[0]
    assert kwargs == {
        "impersonate": "chrome120",
        "proxy": "http://proxy-user:proxy-password@proxy.example:8080",
        "timeout": 20,
        "allow_redirects": True,
    }
    assert "headers" not in kwargs
    assert fake_sentry_span[0].data == {
        "url": "https://example.com/article",
        "proxy_enabled": True,
    }
    assert "proxy.example" not in repr(fake_sentry_span[0].data)
    assert "proxy-user" not in repr(fake_sentry_span[0].data)
    assert "proxy-password" not in repr(fake_sentry_span[0].data)


def test_direct_fetch_span_reports_proxy_disabled(
    fake_sentry_span: list[FakeSpan],
) -> None:
    session = FakeSession(FakeResponse("x" * http_fetch.MIN_HTML_LENGTH))

    asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/article?token=secret"))

    assert fake_sentry_span[0].data == {
        "url": "https://example.com/article",
        "proxy_enabled": False,
    }


@pytest.mark.parametrize("status_code", [429, 500, 503, 599])
def test_transient_statuses_retry(status_code: int) -> None:
    session = FakeSession(FakeResponse("blocked", status_code=status_code))

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/article"))

    assert captured.value.decision is http_fetch.FetchDecision.RETRY
    assert captured.value.status_code == status_code


@pytest.mark.parametrize("error", [Timeout("timed out"), ConnectionError("disconnected")])
def test_transient_network_errors_retry(error: Exception) -> None:
    session = FakeSession(error=error)

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/article"))

    assert captured.value.decision is http_fetch.FetchDecision.RETRY
    assert str(captured.value) == "transient network failure"


def test_proxy_errors_retry() -> None:
    session = FakeSession(error=ProxyError("proxy unreachable"))

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/article"))

    assert captured.value.decision is http_fetch.FetchDecision.RETRY
    assert str(captured.value) == "transient network failure"


@pytest.mark.parametrize(
    ("url", "headers"),
    [
        (
            "https://www.bloomberg.com/news/article",
            {"server": "Varnish", "retry-after": "0", "x-cache": "MISS"},
        ),
        (
            "https://www.reddit.com/r/webscraping/comments/example/.rss",
            {"server": "snooserv", "via": "1.1 varnish", "retry-after": "0"},
        ),
        ("https://arbitrary.example/forbidden", {}),
    ],
)
def test_any_http_403_uses_browser_without_challenge_marker(
    url: str, headers: dict[str, str]
) -> None:
    session = FakeSession(
        FakeResponse("ordinary permission denial", status_code=403, url=url, headers=headers)
    )

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, url))

    assert captured.value.decision is http_fetch.FetchDecision.BROWSER_FALLBACK
    assert captured.value.status_code == 403


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({}, "Please enable JS and disable any ad blocker private@example.com"),
        (
            {"x-cache": "LambdaGeneratedResponse from cloudfront"},
            '<p id="cmsg">Checking your browser</p> private@example.com',
        ),
        (
            {"X-Cache": "edge LAMBDAGENERATEDRESPONSE value"},
            "<style>#cmsg { display: block }</style> private@example.com",
        ),
    ],
)
def test_evidence_backed_http_401_uses_browser_with_exact_marker(
    headers: dict[str, str], body: str
) -> None:
    session = FakeSession(FakeResponse(body, status_code=401, headers=headers))

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/article"))

    assert captured.value.decision is http_fetch.FetchDecision.BROWSER_FALLBACK
    assert captured.value.status_code == 401
    diagnostics = http_fetch.response_diagnostics(
        status_code=401,
        decision=captured.value.decision,
        response_url="https://example.com/article",
        headers=headers,
        body=body,
    )
    assert diagnostics["decision"] == "browser_fallback"
    assert diagnostics["body_markers"] == ["browser_challenge"]
    assert "private@example.com" not in repr(diagnostics)


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({}, "Sign in to your account"),
        ({}, "Permission denied"),
        ({}, "Please enable JavaScript to continue"),
        ({}, '<p id="cmsg">Sign in</p>'),
        ({"x-cache": "LambdaGeneratedResponse from cloudfront"}, "Access denied"),
        ({"x-cache": "MISS"}, '<p id="cmsg">Checking your browser</p>'),
        ({"server": "CloudFront"}, '<p id="cmsg">Checking your browser</p>'),
        ({"x-cache": "LambdaGeneratedResponse"}, "x" * 8192 + "#cmsg"),
        ({}, "x" * 8192 + "Please enable JS and disable any ad blocker"),
    ],
)
def test_ordinary_and_false_positive_http_401_stops_without_marker(
    headers: dict[str, str], body: str
) -> None:
    session = FakeSession(FakeResponse(body, status_code=401, headers=headers))

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/login"))

    assert captured.value.decision is http_fetch.FetchDecision.STOP
    assert captured.value.status_code == 401
    diagnostics = http_fetch.response_diagnostics(
        status_code=401,
        decision=captured.value.decision,
        response_url="https://example.com/login",
        headers=headers,
        body=body,
    )
    assert diagnostics["decision"] == "stop"
    assert diagnostics["body_markers"] == []


@pytest.mark.parametrize(
    ("url", "status_code"),
    [
        ("https://example.com/", 400),
        ("https://example.com/", 404),
        ("https://example.com/", 410),
        ("https://example.com/", 418),
    ],
)
def test_other_permanent_statuses_stop(url: str, status_code: int) -> None:
    session = FakeSession(FakeResponse("blocked", status_code=status_code, url=url))

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, url))

    assert captured.value.decision is http_fetch.FetchDecision.STOP


@pytest.mark.parametrize("body", ["", "short response"])
def test_empty_or_short_regular_content_uses_browser(body: str) -> None:
    session = FakeSession(FakeResponse(body))

    with pytest.raises(http_fetch.FetchAttemptError) as captured:
        asyncio.run(http_fetch.fetch_http_once(session, "https://example.com/article"))

    assert captured.value.decision is http_fetch.FetchDecision.BROWSER_FALLBACK


def test_short_reddit_structured_content_is_accepted() -> None:
    content = "<feed><title>Valid structured response</title></feed>"
    url = "https://www.reddit.com/r/python/comments/abc/title/.rss"
    session = FakeSession(FakeResponse(content, url=url))

    assert asyncio.run(http_fetch.fetch_http_once(session, url)) == content


def test_diagnostics_are_allowlisted_redacted_and_bounded() -> None:
    token = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    diagnostics = http_fetch.response_diagnostics(
        status_code=403,
        decision=http_fetch.FetchDecision.STOP,
        response_url=(
            f"https://user:password@example.com/api_key={token}/article?token={token}#secret"
        ),
        headers={
            "Set-Cookie": f"session={token}",
            "Authorization": f"Bearer {token}",
            "Server": "provider\n edge " + "x" * 400,
            "Location": f"https://user:password@example.com/secret={token}?key={token}",
            "X-Request-ID": token,
            "X-Not-Allowlisted": token,
        },
        body=(
            f"Bearer {token} token={token} password: {token} session={token} "
            "eyJabcdefghijk.abcdefghijkl.abcdefghijkl " + "z" * 3000
        ),
    )

    serialized = repr(diagnostics)
    assert "user" not in serialized
    assert "password@example" not in serialized
    assert token not in serialized
    assert "Set-Cookie" not in serialized
    assert "Authorization" not in serialized
    assert "X-Not-Allowlisted" not in serialized
    assert diagnostics["url"] == "https://example.com/[redacted]/article"
    headers = diagnostics["headers"]
    assert isinstance(headers, dict)
    assert set(headers) == {"server", "location", "x-request-id"}
    assert all(len(value) <= http_fetch.MAX_HEADER_VALUE_LENGTH for value in headers.values())
    assert diagnostics["body_markers"] == []
    for value in (
        "account@example.com",
        "cookie=session-value",
        "ordinary account text",
    ):
        diagnostics = http_fetch.response_diagnostics(
            status_code=403,
            decision=http_fetch.FetchDecision.STOP,
            response_url="https://example.com/",
            headers={},
            body=value,
        )
        assert value not in repr(diagnostics)


@pytest.mark.parametrize("status_code", [401, 403])
@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({}, "Please enable JS and disable any ad blocker private@example.com"),
        (
            {"x-cache": "LambdaGeneratedResponse from cloudfront"},
            "<p id='cmsg'>Checking your browser</p> private@example.com",
        ),
        (
            {"X-Cache": "edge LAMBDAGENERATEDRESPONSE value"},
            "<style>#cmsg { display: block }</style> private@example.com",
        ),
    ],
)
def test_browser_challenge_emits_only_constant_marker(
    status_code: int, headers: dict[str, str], body: str
) -> None:
    diagnostics = http_fetch.response_diagnostics(
        requested_url="https://request.example/article",
        status_code=status_code,
        decision=http_fetch.FetchDecision.STOP,
        response_url="https://redirect.example/challenge",
        headers=headers,
        body=body,
    )
    assert diagnostics["body_markers"] == ["browser_challenge"]
    assert "private@example.com" not in repr(diagnostics)


@pytest.mark.parametrize(
    ("status_code", "headers", "body"),
    [
        (200, {}, "Please enable JS and disable any ad blocker"),
        (401, {}, "<p id='cmsg'>Sign in</p>"),
        (403, {"x-cache": "MISS"}, "<style>#cmsg{}</style>"),
        (403, {"x-cache": "LambdaGeneratedResponse"}, "Access denied"),
        (401, {}, "Please enable JavaScript to continue"),
        (401, {}, "Sign in to your account"),
        (403, {"server": "Varnish", "retry-after": "0"}, "Permission denied"),
        (403, {"server": "snooserv", "via": "1.1 varnish"}, "Forbidden"),
        (403, {}, "x" * 8192 + "Please enable JS and disable any ad blocker"),
    ],
)
def test_browser_challenge_marker_rejects_false_positives(
    status_code: int, headers: dict[str, str], body: str
) -> None:
    diagnostics = http_fetch.response_diagnostics(
        status_code=status_code,
        decision=http_fetch.FetchDecision.STOP,
        response_url="https://example.com/",
        headers=headers,
        body=body,
    )
    assert diagnostics["body_markers"] == []
