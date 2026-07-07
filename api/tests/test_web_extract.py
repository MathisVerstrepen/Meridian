import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.web import web_extract


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


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        (
            "https://www.reddit.com/r/Python/comments/abc/title/",
            "https://www.reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "reddit.com/r/Python/comments/abc/title/",
            "https://reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "https://reddit.com/r/Python/comments/abc/title",
            "https://reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "old.reddit.com/r/Python/comments/abc/title/",
            "https://old.reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "https://old.reddit.com/r/Python/comments/abc/title/",
            "https://old.reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "www.reddit.com/r/Python/comments/abc/title/",
            "https://www.reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "https://www.reddit.com/r/Python/comments/abc/title/.json",
            "https://www.reddit.com/r/Python/comments/abc/title/.json",
        ),
        (
            "https://www.reddit.com/r/Python/comments/abc/title/.rss",
            "https://www.reddit.com/r/Python/comments/abc/title/.rss",
        ),
        (
            "https://www.reddit.com/r/Python/comments/abc/title/?sort=top",
            "https://www.reddit.com/r/Python/comments/abc/title/.rss?sort=top",
        ),
        (
            "https://www.reddit.com/r/Python/comments/abc/title/.json?sort=top",
            "https://www.reddit.com/r/Python/comments/abc/title/.json?sort=top",
        ),
    ],
)
def test_preprocess_url_normalizes_reddit_variants(raw_url: str, expected_url: str) -> None:
    normalized_url, is_direct_content = asyncio.run(web_extract._preprocess_url(raw_url))

    assert normalized_url == expected_url
    assert is_direct_content is False


def test_url_to_markdown_fetches_and_parses_reddit_atom(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched_urls = []

    async def fake_attempt_fetch(session: object, url: str, proxy: str | None = None) -> str:
        fetched_urls.append(url)
        return REDDIT_ATOM

    monkeypatch.setattr(web_extract, "_attempt_fetch", fake_attempt_fetch)

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

    async def fake_attempt_fetch(session: object, url: str, proxy: str | None = None) -> str:
        fetched_urls.append(url)
        return REDDIT_ATOM

    monkeypatch.setattr(web_extract, "_attempt_fetch", fake_attempt_fetch)

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

    async def fake_attempt_fetch(session: object, url: str, proxy: str | None = None) -> str:
        assert url == "https://reddit.com/r/Python/comments/abc/json_post/.json?sort=top"
        return json.dumps(reddit_json)

    monkeypatch.setattr(web_extract, "_attempt_fetch", fake_attempt_fetch)

    result = asyncio.run(
        web_extract.url_to_markdown(
            "https://reddit.com/r/Python/comments/abc/json_post/.json?sort=top"
        )
    )

    assert result is not None
    assert "# JSON post title" in result
    assert "JSON post body" in result
    assert "JSON comment body" in result


class _FakeSpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def set_data(self, key: str, value: str) -> None:
        pass

    def set_status(self, status: str) -> None:
        pass


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


class _FakeSession:
    def __init__(self, text: str) -> None:
        self.text = text
        self.urls = []

    async def get(self, url: str, **kwargs) -> _FakeResponse:
        self.urls.append(url)
        return _FakeResponse(self.text)


def test_attempt_fetch_accepts_short_reddit_structured_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_extract, "get_browser_headers", lambda url: {})
    monkeypatch.setattr(web_extract.sentry_sdk, "start_span", lambda **kwargs: _FakeSpan())

    session = _FakeSession(REDDIT_ATOM)

    result = asyncio.run(
        web_extract._attempt_fetch(
            session,
            "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/.rss?sort=top",
        )
    )

    assert result == REDDIT_ATOM
    assert session.urls == [
        "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/.rss?sort=top"
    ]


def test_attempt_fetch_rejects_empty_reddit_structured_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_extract, "get_browser_headers", lambda url: {})
    monkeypatch.setattr(web_extract.sentry_sdk, "start_span", lambda **kwargs: _FakeSpan())
    monkeypatch.setattr(web_extract.sentry_sdk, "capture_exception", lambda error: None)

    session = _FakeSession("   ")

    with pytest.raises(Exception, match="Empty content"):
        asyncio.run(
            web_extract._attempt_fetch(
                session,
                "https://www.reddit.com/r/Python/comments/1ra2yt2/why_python/.rss",
            )
        )
