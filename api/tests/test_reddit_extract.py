import asyncio
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.web import reddit, web_extract


OLD_REDDIT_HTML = """
<html>
  <body>
    <div id="header">HEADER CHROME SENTINEL</div>
    <div class="side">SIDEBAR CHROME SENTINEL</div>
    <div class="content" role="main">
      <div class="thing link self">
        <form class="usertext">
          <div class="usertext-body">
            <p>POST BODY SENTINEL. The post explains a detailed extraction problem with
            enough useful context for readers. It describes expected behavior, observed
            behavior, reproducible inputs, and why retaining the original discussion is
            important for a complete answer.</p>
          </div>
          <button>POST CONTROL SENTINEL</button>
        </form>
      </div>
      <div class="commentarea">
        <div class="comment">
          <form class="usertext">
            <div class="usertext-body">
              <p>TOP LEVEL COMMENT SENTINEL. This response gives a substantial explanation
              of semantic content selection, safe cleanup, deterministic conversion, and
              the value of keeping rendered prose while excluding unrelated controls.</p>
            </div>
            <button>TOP LEVEL CONTROL SENTINEL</button>
          </form>
          <div class="child">
            <div class="comment">
              <form class="usertext">
                <div class="usertext-body">
                  <p>NESTED COMMENT SENTINEL. This nested reply adds further practical
                  details about preserving document order, handling fallback markup, and
                  testing the resulting Markdown without relying on a live website.</p>
                </div>
                <button>NESTED CONTROL SENTINEL</button>
              </form>
            </div>
          </div>
        </div>
        <form class="reply"><button>REPLY FORM CONTROL SENTINEL</button></form>
      </div>
    </div>
  </body>
</html>
"""


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class FakeBrowserManager:
    def __init__(self, html: str) -> None:
        self.html = html
        self.requested_urls: list[str] = []

    async def fetch(self, url: str) -> str:
        self.requested_urls.append(url)
        return self.html


class UnexpectedProxyManager:
    proxies = [{"http": "http://unused:8080", "https": "http://unused:8080"}]

    async def get_proxy(self) -> dict[str, str]:
        raise AssertionError("A classified 403 must bypass ordinary proxies")


def _convert_old_reddit_html(html: str) -> str:
    prepared = reddit._prepare_reddit_html_for_markdown(html)
    cleaned = web_extract.clean_html(prepared)
    return web_extract.convert_to_markdown(cleaned, "https://old.reddit.com/r/test/comments/abc/")


def _assert_body_content_without_chrome(markdown: str) -> None:
    post_position = markdown.index("POST BODY SENTINEL")
    top_level_position = markdown.index("TOP LEVEL COMMENT SENTINEL")
    nested_position = markdown.index("NESTED COMMENT SENTINEL")

    assert post_position < top_level_position < nested_position
    for omitted_sentinel in (
        "HEADER CHROME SENTINEL",
        "SIDEBAR CHROME SENTINEL",
        "POST CONTROL SENTINEL",
        "TOP LEVEL CONTROL SENTINEL",
        "NESTED CONTROL SENTINEL",
        "REPLY FORM CONTROL SENTINEL",
    ):
        assert omitted_sentinel not in markdown


def test_prepare_reddit_html_retains_post_and_comment_bodies() -> None:
    markdown = _convert_old_reddit_html(OLD_REDDIT_HTML)

    _assert_body_content_without_chrome(markdown)


def test_reddit_browser_fallback_retains_old_reddit_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = FakeBrowserManager(OLD_REDDIT_HTML)
    fetch_calls: list[tuple[str, str | None]] = []

    async def fake_fetch(session: object, url: str, proxy: str | None = None) -> str:
        fetch_calls.append((url, proxy))
        raise web_extract.FetchAttemptError(
            web_extract.FetchDecision.BROWSER_FALLBACK,
            "Reddit rejected the direct RSS request",
            403,
        )

    monkeypatch.setattr(web_extract, "AsyncSession", FakeSession)
    monkeypatch.setattr(web_extract, "proxy_manager", UnexpectedProxyManager())
    monkeypatch.setattr(web_extract, "browser_fetch_manager", browser)
    monkeypatch.setattr(web_extract, "fetch_http_once", fake_fetch)

    markdown = asyncio.run(
        web_extract.url_to_markdown("https://www.reddit.com/r/test/comments/abc/thread_title/")
    )

    assert fetch_calls == [
        ("https://www.reddit.com/r/test/comments/abc/thread_title/.rss", None)
    ]
    assert browser.requested_urls == [
        "https://old.reddit.com/r/test/comments/abc/thread_title/"
    ]
    _assert_body_content_without_chrome(markdown)
