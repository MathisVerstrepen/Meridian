import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.web import web_extract
from services.web.browser_fetch import BrowserFetchError
from services.web.fetch_errors import LinkExtractionError, LinkExtractionFailureReason

REDDIT_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Why Python still dominates in 2026 despite everything</title>
  <updated>2026-07-07T10:00:00+00:00</updated>
  <link href="https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/" />
  <entry>
    <title>Why Python still dominates in 2026 despite everything</title>
    <author><name>/u/post_author</name></author>
    <updated>2026-07-07T10:00:00+00:00</updated>
    <link href="https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/" />
    <content type="html">&lt;p&gt;Python remains popular because the ecosystem is broad.&lt;/p&gt;</content>
  </entry>
  <entry>
    <title>Comment by /u/commenter</title>
    <author><name>/u/commenter</name></author>
    <updated>2026-07-07T10:01:00+00:00</updated>
    <link href="https://www.reddit.com/r/Python/comments/1ra2yt2/comment/c1/" />
    <content type="html">&lt;p&gt;The standard library and packaging improvements help.&lt;/p&gt;</content>
  </entry>
</feed>
"""


def test_convert_to_markdown_preserves_anchor_text_and_destination() -> None:
    html = (
        '<main><p>Continue to the <a href="https://external.example/next">'
        "next page</a>.</p></main>"
    )

    result = web_extract.convert_to_markdown(html, "https://example.com/article")

    assert "[next page](https://external.example/next)" in result


def test_extract_navigation_links_filters_normalizes_and_preserves_source_order() -> None:
    html = """
    <body>
      <nav>
        <a href=" https://outside.example/path?x=1#part "> Outside </a>
        <a href="next?page=2#details">  Next <span> page </span> </a>
        <a href="/root">Root</a>
        <a href="?page=3">Query</a>
        <a href="//cdn.example/menu">Protocol relative</a>
        <a href="next?page=2#details">Duplicate</a>
        <a href="https://empty.example"></a>
        <a>No href</a>
        <a href=" ">Empty</a>
        <a href="#local">Fragment only</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="javascript:void(0)">Script</a>
        <a href="data:text/plain,menu">Data</a>
        <a href="http:relative">Hostless</a>
        <a href="https://[broken">Malformed</a>
      </nav>
      <main><a href="https://body.example">Body link</a></main>
    </body>
    """

    result = web_extract.extract_navigation_links(html, "https://example.com/docs/article?old=1")

    assert result == [
        {"title": "Outside", "url": "https://outside.example/path?x=1#part"},
        {"title": "Next page", "url": "https://example.com/docs/next?page=2#details"},
        {"title": "Root", "url": "https://example.com/root"},
        {"title": "Query", "url": "https://example.com/docs/article?page=3"},
        {"title": "Protocol relative", "url": "https://cdn.example/menu"},
        {"title": "Duplicate", "url": "https://example.com/docs/next?page=2#details"},
        {"title": "", "url": "https://empty.example"},
    ]


def test_extract_navigation_links_caps_first_fifty_qualifying_links() -> None:
    anchors = ['<a href="#ignored">Ignored</a>']
    anchors.extend(
        '<a href="/same"></a>' if index in {1, 2} else f'<a href="/page/{index}">Page {index}</a>'
        for index in range(55)
    )
    anchors.insert(25, '<a href="mailto:ignored@example.com">Ignored</a>')

    result = web_extract.extract_navigation_links(
        f"<nav>{''.join(anchors)}</nav>", "https://example.com/start"
    )

    expected_urls = [
        "https://example.com/same" if index in {1, 2} else f"https://example.com/page/{index}"
        for index in range(50)
    ]
    assert len(result) == web_extract.MAX_NAVIGATION_LINKS == 50
    assert [link["url"] for link in result] == expected_urls
    assert result[1] == {"title": "", "url": "https://example.com/same"}
    assert result[2] == result[1]
    assert "https://example.com/page/50" not in expected_urls


def test_url_to_markdown_remains_a_string_compatibility_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def structured_extraction(url: str) -> web_extract.PageExtractionResult:
        return {
            "markdown_content": "# Compatible",
            "navigation_links": [{"title": "Next", "url": "https://example.com/next"}],
        }

    monkeypatch.setattr(web_extract, "_extract_web_page", structured_extraction)

    result = asyncio.run(web_extract.url_to_markdown("https://example.com"))

    assert result == "# Compatible"
    assert isinstance(result, str)


@pytest.mark.parametrize(
    ("raw_url", "expected_fetch_url", "expected_browser_url"),
    [
        (
            "https://www.reddit.com/r/Python/comments/abc/title/",
            "https://www.reddit.com/r/Python/comments/abc/title/.rss",
            "https://old.reddit.com/r/Python/comments/abc/title/",
        ),
        (
            "reddit.com/r/Python/comments/abc/title/",
            "https://reddit.com/r/Python/comments/abc/title/.rss",
            "https://old.reddit.com/r/Python/comments/abc/title/",
        ),
        (
            "https://reddit.com/r/Python/comments/abc/title",
            "https://reddit.com/r/Python/comments/abc/title/.rss",
            "https://old.reddit.com/r/Python/comments/abc/title/",
        ),
        (
            "old.reddit.com/r/Python/comments/abc/title/",
            "https://old.reddit.com/r/Python/comments/abc/title/.rss",
            "https://old.reddit.com/r/Python/comments/abc/title/",
        ),
        (
            "http://old.reddit.com/r/Python/comments/abc/title/?sort=top#comments",
            "http://old.reddit.com/r/Python/comments/abc/title/.rss?sort=top#comments",
            "https://old.reddit.com/r/Python/comments/abc/title/?sort=top#comments",
        ),
        (
            "https://www.reddit.com/r/Python/comments/abc/title/.json",
            "https://www.reddit.com/r/Python/comments/abc/title/.json",
            "https://old.reddit.com/r/Python/comments/abc/title/",
        ),
        (
            "https://www.reddit.com/r/Python/comments/abc/title/.RSS/",
            "https://www.reddit.com/r/Python/comments/abc/title/.RSS/",
            "https://old.reddit.com/r/Python/comments/abc/title/",
        ),
        (
            "https://reddit.com/r/Python/comments/abc/title.json/?raw_json=1#comments",
            "https://reddit.com/r/Python/comments/abc/title.json/?raw_json=1#comments",
            "https://old.reddit.com/r/Python/comments/abc/title/?raw_json=1#comments",
        ),
        (
            "old.reddit.com",
            "https://old.reddit.com/.rss",
            "https://old.reddit.com/",
        ),
    ],
)
def test_preprocess_url_normalizes_reddit_variants(
    raw_url: str,
    expected_fetch_url: str,
    expected_browser_url: str,
) -> None:
    normalized_url, is_direct_content = asyncio.run(web_extract._preprocess_url(raw_url))

    assert normalized_url == expected_fetch_url
    assert web_extract._normalize_reddit_url_for_browser(raw_url) == expected_browser_url
    assert is_direct_content is False


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/article.json?sort=top#comments",
        "https://reddit.example/r/Python/post.rss",
        "https://np.reddit.com/r/Python/post.rss",
        "https://user@reddit.com/r/Python/post.rss",
        "https://reddit.com:443/r/Python/post.rss",
    ],
)
def test_reddit_browser_normalization_rejects_unsupported_authorities(url: str) -> None:
    assert web_extract._normalize_reddit_url_for_browser(url) == url


def test_url_to_markdown_fetches_and_parses_reddit_atom(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched_urls = []

    async def fake_http_fetch(session: object, url: str, proxy: str | None = None) -> str:
        fetched_urls.append(url)
        return REDDIT_ATOM

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_http_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/?sort=top"
        )
    )

    assert fetched_urls == [
        "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/.rss?sort=top"
    ]
    assert result is not None
    assert "# Why Python still dominates in 2026 despite everything" in result
    assert "Python remains popular because the ecosystem is broad." in result
    assert "The standard library and packaging improvements help." in result


def test_url_to_markdown_keeps_and_parses_existing_reddit_rss_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched_urls = []

    async def fake_http_fetch(session: object, url: str, proxy: str | None = None) -> str:
        fetched_urls.append(url)
        return REDDIT_ATOM

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_http_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/.rss?sort=top"
        )
    )

    assert fetched_urls == [
        "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/.rss?sort=top"
    ]
    assert result is not None
    assert "# Why Python still dominates in 2026 despite everything" in result
    assert "Python remains popular because the ecosystem is broad." in result


def test_url_to_markdown_keeps_and_parses_reddit_json_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reddit_json = [
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "JSON post title",
                            "author": "post_author",
                            "subreddit_name_prefixed": "r/Python",
                            "score": 42,
                            "num_comments": 1,
                            "selftext": "JSON post body",
                            "is_self": True,
                            "permalink": "/r/Python/comments/abc/json_post/",
                        }
                    }
                ]
            }
        },
        {
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "author": "commenter",
                            "body": "JSON comment body",
                            "score": 5,
                            "replies": "",
                        },
                    }
                ]
            }
        },
    ]

    async def fake_http_fetch(session: object, url: str, proxy: str | None = None) -> str:
        assert url == "https://reddit.com/r/Python/comments/abc/json_post/.json?sort=top"
        return json.dumps(reddit_json)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_http_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://reddit.com/r/Python/comments/abc/json_post/.json?sort=top"
        )
    )

    assert result is not None
    assert "# JSON post title" in result
    assert "JSON post body" in result
    assert "JSON comment body" in result


VALID_HTML = "<main><h1>Article</h1><p>" + "useful content " * 100 + "</p></main>"


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class FakeProxyManager:
    def __init__(self, proxies: list[str]) -> None:
        self.proxies = [{"http": proxy, "https": proxy} for proxy in proxies]
        self.index = 0

    async def get_proxy(self) -> dict[str, str] | None:
        if not self.proxies:
            return None
        proxy = self.proxies[self.index % len(self.proxies)]
        self.index += 1
        return proxy


class FakeBrowserManager:
    def __init__(self, events: list[str], result: str = VALID_HTML, error: Exception | None = None):
        self.events = events
        self.result = result
        self.error = error
        self.requested_urls: list[str] = []

    async def fetch(self, url: str) -> str:
        self.requested_urls.append(url)
        self.events.append("browser")
        if self.error is not None:
            raise self.error
        return self.result


def configure_orchestration(
    monkeypatch: pytest.MonkeyPatch,
    proxies: list[str],
    browser: FakeBrowserManager,
) -> None:
    monkeypatch.setattr(web_extract, "AsyncSession", FakeSession)
    monkeypatch.setattr(web_extract, "proxy_manager", FakeProxyManager(proxies))
    monkeypatch.setattr(web_extract, "browser_fetch_manager", browser)


def fetch_error(
    decision: web_extract.FetchDecision,
    status_code: int | None = None,
) -> web_extract.FetchAttemptError:
    return web_extract.FetchAttemptError(decision, "classified failure", status_code)


def test_extract_web_page_returns_empty_navigation_for_direct_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def direct_markdown(url: str) -> tuple[str, bool]:
        return "# Local paper", True

    monkeypatch.setattr(web_extract, "_preprocess_url", direct_markdown)

    result = asyncio.run(web_extract.extract_web_page("https://arxiv.org/abs/1234.5678"))

    assert result == {"markdown_content": "# Local paper", "navigation_links": []}


def test_navigation_links_belong_only_to_successful_fallback_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    failed_proxy_html = '<nav><a href="/failed">Failed attempt</a></nav><main><p>short</p></main>'
    browser_html = '<nav><a href="/browser-next"> Browser <span>next</span> </a></nav>' + VALID_HTML
    browser = FakeBrowserManager(events, result=browser_html)
    configure_orchestration(monkeypatch, ["http://one:8080"], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        if proxy is None:
            raise fetch_error(web_extract.FetchDecision.RETRY)
        return failed_proxy_html

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.extract_web_page("https://example.com/article"))

    assert events == ["direct", "http://one:8080", "browser"]
    assert result["navigation_links"] == [
        {"title": "Browser next", "url": "https://example.com/browser-next"}
    ]
    assert "Browser next" not in result["markdown_content"]
    assert "Failed attempt" not in result["markdown_content"]


def test_direct_reddit_rss_success_uses_fetch_url_without_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, [], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(f"direct:{url}")
        return REDDIT_ATOM

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown("reddit.com/r/Python/comments/abc/title?sort=top#comments")
    )

    assert events == [
        "direct:https://reddit.com/r/Python/comments/abc/title/.rss?sort=top#comments"
    ]
    assert browser.requested_urls == []
    assert result.startswith("# Why Python still dominates")


def test_proxy_reddit_rss_success_keeps_structured_fetch_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, ["http://one:8080"], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(f"{proxy or 'direct'}:{url}")
        if proxy is None:
            raise fetch_error(web_extract.FetchDecision.RETRY)
        return REDDIT_ATOM

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown("https://www.reddit.com/r/Python/comments/abc/title/")
    )

    fetch_url = "https://www.reddit.com/r/Python/comments/abc/title/.rss"
    assert events == [f"direct:{fetch_url}", f"http://one:8080:{fetch_url}"]
    assert browser.requested_urls == []
    assert result.startswith("# Why Python still dominates")


def test_direct_reddit_fallback_uses_old_reddit_html_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, ["http://unused:8080"], browser)
    requested_urls: list[str] = []

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        requested_urls.append(url)
        events.append("direct")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://www.reddit.com/r/Python/comments/abc/title?sort=top#comments"
        )
    )

    assert requested_urls == [
        "https://www.reddit.com/r/Python/comments/abc/title/.rss?sort=top#comments"
    ]
    assert browser.requested_urls == [
        "https://old.reddit.com/r/Python/comments/abc/title/?sort=top#comments"
    ]
    assert events == ["direct", "browser"]
    assert "# Article" in result
    assert "Reddit RSS" not in result


def test_proxy_reddit_structured_fallback_uses_suffix_free_browser_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, ["http://one:8080", "http://unused:8080"], browser)
    requested_urls: list[tuple[str, str]] = []

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        requested_urls.append((proxy or "direct", url))
        events.append(proxy or "direct")
        decision = (
            web_extract.FetchDecision.RETRY
            if proxy is None
            else web_extract.FetchDecision.BROWSER_FALLBACK
        )
        raise fetch_error(decision, 403 if proxy else None)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://reddit.com/r/Python/comments/abc/title/.JSON/?raw_json=1#comments"
        )
    )

    fetch_url = "https://reddit.com/r/Python/comments/abc/title/.JSON/?raw_json=1#comments"
    assert requested_urls == [("direct", fetch_url), ("http://one:8080", fetch_url)]
    assert browser.requested_urls == [
        "https://old.reddit.com/r/Python/comments/abc/title/?raw_json=1#comments"
    ]
    assert events == ["direct", "http://one:8080", "browser"]
    assert "# Article" in result


def test_non_reddit_browser_url_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, [], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(f"direct:{url}")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    source_url = "https://example.com/article.json?sort=top#section"
    result = asyncio.run(web_extract.url_to_markdown(source_url))

    assert result is not None
    assert events == [f"direct:{source_url}", "browser"]
    assert browser.requested_urls == [source_url]


def test_direct_bloomberg_style_403_bypasses_proxies_and_uses_browser_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, ["http://proxy-one:8080"], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("proxy" if proxy else "direct")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.url_to_markdown("https://www.bloomberg.com/news/article"))

    assert result is not None
    assert events == ["direct", "browser"]


def test_direct_evidence_backed_401_bypasses_proxies_and_uses_browser_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        ["http://proxy-one:8080"],
        FakeBrowserManager(events),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 401)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.url_to_markdown("https://example.com/challenged"))

    assert result is not None
    assert events == ["direct", "browser"]


def test_direct_ordinary_401_stops_without_proxy_or_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        ["http://proxy-one:8080"],
        FakeBrowserManager(events),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        raise fetch_error(web_extract.FetchDecision.STOP, 401)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(web_extract.url_to_markdown("https://example.com/login"))

    assert captured.value.reason is LinkExtractionFailureReason.HTTP_REJECTED
    assert captured.value.status_code == 401
    assert events == ["direct"]


def test_direct_permanent_failure_stops_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        ["http://proxy-one:8080"],
        FakeBrowserManager(events),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("proxy" if proxy else "direct")
        raise fetch_error(web_extract.FetchDecision.STOP, 404)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(web_extract.url_to_markdown("https://example.com/missing"))

    assert captured.value.reason is LinkExtractionFailureReason.HTTP_REJECTED
    assert captured.value.status_code == 404
    assert events == ["direct"]


def test_transient_failure_rotates_up_to_three_proxies_and_returns_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    proxies = ["http://one:8080", "http://two:8080", "http://three:8080", "http://four:8080"]
    configure_orchestration(monkeypatch, proxies, FakeBrowserManager(events))

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        if proxy == "http://three:8080":
            return VALID_HTML
        raise fetch_error(web_extract.FetchDecision.RETRY)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert result is not None
    assert events == ["direct", *proxies[:3]]


def test_proxy_reddit_style_403_stops_rotation_and_uses_browser_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        ["http://one:8080", "http://two:8080"],
        FakeBrowserManager(events),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        if proxy is None:
            raise fetch_error(web_extract.FetchDecision.RETRY)
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://www.reddit.com/r/webscraping/comments/example/article/.rss"
        )
    )

    assert result is not None
    assert events == ["direct", "http://one:8080", "browser"]


def test_proxy_evidence_backed_401_stops_rotation_and_uses_browser_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        ["http://one:8080", "http://two:8080"],
        FakeBrowserManager(events),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        if proxy is None:
            raise fetch_error(web_extract.FetchDecision.RETRY)
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 401)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.url_to_markdown("https://example.com/challenged"))

    assert result is not None
    assert events == ["direct", "http://one:8080", "browser"]


def test_proxy_ordinary_401_stops_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        ["http://one:8080", "http://two:8080"],
        FakeBrowserManager(events),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        decision = (
            web_extract.FetchDecision.RETRY if proxy is None else web_extract.FetchDecision.STOP
        )
        raise fetch_error(decision, 401 if proxy is not None else None)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert captured.value.reason is LinkExtractionFailureReason.HTTP_REJECTED
    assert captured.value.status_code == 401
    assert events == ["direct", "http://one:8080"]


@pytest.mark.parametrize("proxies", [[], ["http://one:8080", "http://two:8080"]])
def test_exhausted_or_empty_proxy_pool_uses_browser(
    monkeypatch: pytest.MonkeyPatch,
    proxies: list[str],
) -> None:
    events: list[str] = []
    configure_orchestration(monkeypatch, proxies, FakeBrowserManager(events))

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(proxy or "direct")
        raise fetch_error(web_extract.FetchDecision.RETRY)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert result is not None
    assert events[-1] == "browser"
    assert events[:-1] == ["direct", *proxies]


def test_unexpected_browser_failure_is_safely_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch,
        [],
        FakeBrowserManager(events, error=RuntimeError("browser unavailable")),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("direct")
        raise fetch_error(web_extract.FetchDecision.RETRY)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert captured.value.reason is LinkExtractionFailureReason.BROWSER_FAILED
    assert events == ["direct", "browser"]


@pytest.mark.parametrize(
    "reason",
    [
        LinkExtractionFailureReason.CONNECTIVITY_EXHAUSTED,
        LinkExtractionFailureReason.CHALLENGE_UNRESOLVED,
        LinkExtractionFailureReason.HTTP_REJECTED,
    ],
)
def test_browser_typed_failure_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    reason: LinkExtractionFailureReason,
) -> None:
    events: list[str] = []
    status_code = 403 if reason is LinkExtractionFailureReason.HTTP_REJECTED else None
    browser_error = BrowserFetchError(reason, status_code)
    configure_orchestration(monkeypatch, [], FakeBrowserManager(events, error=browser_error))

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("direct")
        raise fetch_error(web_extract.FetchDecision.RETRY)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert captured.value is browser_error
    assert captured.value.reason is reason
    assert captured.value.status_code == status_code
    assert events == ["direct", "browser"]


def test_reddit_browser_typed_failure_preserves_identity_and_uses_html_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser_error = BrowserFetchError(LinkExtractionFailureReason.HTTP_REJECTED, 403)
    browser = FakeBrowserManager(events, error=browser_error)
    configure_orchestration(monkeypatch, [], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(f"direct:{url}")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(
            web_extract.url_to_markdown(
                "https://www.reddit.com/r/Python/comments/abc/title/.rss?sort=top#comments"
            )
        )

    assert captured.value is browser_error
    assert captured.value.reason is LinkExtractionFailureReason.HTTP_REJECTED
    assert captured.value.status_code == 403
    assert browser.requested_urls == [
        "https://old.reddit.com/r/Python/comments/abc/title/?sort=top#comments"
    ]
    assert events == [
        "direct:https://www.reddit.com/r/Python/comments/abc/title/.rss?sort=top#comments",
        "browser",
    ]


def test_reddit_phase_logs_use_only_sanitized_phase_target(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, [], browser)

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("direct")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)
    source_url = (
        "https://www.reddit.com/r/Python/comments/"
        "abcdefghijklmnopqrstuvwxyz123456/title?token=query-secret#fragment-secret"
    )

    with caplog.at_level("INFO", logger="uvicorn.error"):
        asyncio.run(web_extract.url_to_markdown(source_url))

    direct_record = next(
        record for record in caplog.records if "Direct fetch attempt" in record.message
    )
    browser_record = next(
        record for record in caplog.records if "Falling back to headless browser" in record.message
    )
    assert "https://www.reddit.com/r/Python/comments/[redacted]/title/.rss" in direct_record.message
    assert "old.reddit.com" not in direct_record.message
    assert "https://old.reddit.com/r/Python/comments/[redacted]/title/" in browser_record.message
    assert ".rss" not in browser_record.message
    assert "query-secret" not in caplog.text
    assert "fragment-secret" not in caplog.text
    assert "abcdefghijklmnopqrstuvwxyz123456" not in caplog.text


def test_browser_html_with_insufficient_markdown_is_unusable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    configure_orchestration(
        monkeypatch, [], FakeBrowserManager(events, result="<main>short</main>")
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("direct")
        raise fetch_error(web_extract.FetchDecision.RETRY)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    with pytest.raises(LinkExtractionError) as captured:
        asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert captured.value.reason is LinkExtractionFailureReason.UNUSABLE_CONTENT
    assert events == ["direct", "browser"]


def test_insufficient_direct_markdown_uses_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    configure_orchestration(monkeypatch, ["http://proxy:8080"], FakeBrowserManager(events))

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append("proxy" if proxy else "direct")
        return "<main><p>short</p></main>"

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    result = asyncio.run(web_extract.url_to_markdown("https://example.com/article"))

    assert result is not None
    assert events == ["direct", "browser"]


def test_preprocess_arxiv_still_returns_local_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_extract, "arxiv_to_md", lambda pdf_url, temp_dir: "# Local paper")

    content, is_direct = asyncio.run(web_extract._preprocess_url("https://arxiv.org/abs/1234.5678"))

    assert content == "# Local paper"
    assert is_direct is True


def test_failed_arxiv_preprocessing_keeps_fetch_and_browser_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    browser = FakeBrowserManager(events)
    configure_orchestration(monkeypatch, [], browser)
    monkeypatch.setattr(
        web_extract,
        "arxiv_to_md",
        lambda pdf_url, temp_dir: (_ for _ in ()).throw(RuntimeError("conversion failed")),
    )

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        events.append(f"direct:{url}")
        raise fetch_error(web_extract.FetchDecision.BROWSER_FALLBACK, 403)

    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    source_url = "https://arxiv.org/abs/1234.5678?download=1#page=2"
    result = asyncio.run(web_extract.url_to_markdown(source_url))

    assert result is not None
    assert events == [f"direct:{source_url}", "browser"]
    assert browser.requested_urls == [source_url]
