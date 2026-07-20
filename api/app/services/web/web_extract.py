import asyncio
import json
import logging
import tempfile
from functools import partial

from arxiv2text import arxiv_to_md
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from markdownify import markdownify as md
from services.proxies import proxy_manager
from services.web.browser_fetch import browser_fetch_manager
from services.web.fetch_errors import LinkExtractionError, LinkExtractionFailureReason
from services.web.http_fetch import FetchAttemptError, FetchDecision, fetch_http_once, sanitize_url
from services.web.reddit import (
    _ensure_url_scheme,
    _is_reddit_json_url,
    _is_reddit_rss_url,
    _is_reddit_structured_url,
    _is_reddit_url,
    _normalize_reddit_url_for_browser,
    _normalize_reddit_url_for_fetch,
    _parse_reddit_json_to_markdown,
    _parse_reddit_rss_to_markdown,
    _prepare_reddit_html_for_markdown,
)

logger = logging.getLogger("uvicorn.error")

MIN_MARKDOWN_LENGTH = 500


def clean_html(html_content: str) -> str:
    """
    Cleans HTML by extracting the main content and removing clutter.

    Args:
        html_content: Raw HTML string.

    Returns:
        A string of the cleaned HTML content.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # 1. First, try to find the main content block. This is the most reliable method.
    main_content = soup.find("main")
    if not main_content:
        main_content = soup.find("article")
    if not main_content:
        # As a last resort, use the whole body.
        main_content = soup.body
        if not main_content:
            return ""

    # 2. Remove all non-semantic or noisy tags
    tags_to_remove = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "iframe",
        "noscript",
    ]
    for tag in main_content.find_all(tags_to_remove):
        tag.decompose()

    # 3. Remove comments
    for comment in main_content.find_all(
        string=lambda text: isinstance(text, str) and text.find("<!--") != -1
    ):
        comment.extract()

    # Remove empty tags that might be left after cleaning
    for tag in main_content.find_all():
        if (
            not tag.get_text(strip=True)
            and not tag.find_all(recursive=False)
            and tag.name not in ["img", "hr"]
        ):
            tag.decompose()

    return str(main_content)


def convert_to_markdown(html_snippet: str, base_url: str) -> str:
    """
    Converts a clean HTML snippet to AI-ready Markdown.

    Args:
        html_snippet: The cleaned HTML string.
        base_url: The original URL, used to resolve relative links/images.

    Returns:
        A clean Markdown string.
    """
    markdown_text = md(
        html_snippet,
        heading_style="ATX",  # Use '#' for headings
        bullets="*",  # Use '*' for list items
        convert_images=False,  # Do not convert images
        strip=["a", "img"],  # Strip links and images but keep their text/alt text
        autolinks=False,  # Don't automatically convert URLs to links
        base_url=base_url,  # Helps resolve relative image/link paths
    )
    return markdown_text or ""


async def _preprocess_url(url: str) -> tuple[str, bool]:
    """
    Preprocesses the URL to ensure it is well-formed.
    """
    url = _ensure_url_scheme(url)

    if _is_reddit_url(url):
        url = _normalize_reddit_url_for_fetch(url)

    if "arxiv.org" in url:
        parts = url.split("/")
        paper_id = parts[-1] if parts[-1] else parts[-2]
        pdf_url = f"https://arxiv.org/pdf/{paper_id}"

        try:
            loop = asyncio.get_running_loop()
            with tempfile.TemporaryDirectory() as temp_dir:
                content = await loop.run_in_executor(None, partial(arxiv_to_md, pdf_url, temp_dir))
                return str(content), True
        except Exception as error:
            logging.error("Failed to process arXiv URL locally (%s)", type(error).__name__)
            pass

    return url, False


async def url_to_markdown(url: str) -> str:
    """Return extracted Markdown or raise a controlled ``LinkExtractionError``."""
    safe_url = sanitize_url(url)
    try:
        return await _url_to_markdown(url)
    except LinkExtractionError:
        raise
    except Exception as error:
        logger.error(
            "Unexpected link extraction failure for %s (%s)",
            safe_url,
            type(error).__name__,
        )
        raise LinkExtractionError(LinkExtractionFailureReason.FETCH_FAILED) from error


async def _url_to_markdown(url: str) -> str:
    """
    Fetches a URL with a robust retry and fallback strategy, then converts its
    main content to Markdown.

    Only transient direct failures enter the ordinary proxy pool. Provider blocks or
    unusable content go directly to the reusable browser fallback.
    """
    MAX_DIRECT_ATTEMPTS = 1
    MAX_PROXY_ATTEMPTS = 3
    browser_url = _normalize_reddit_url_for_browser(url)
    fetch_url, is_direct_content = await _preprocess_url(url)
    if is_direct_content:
        if not fetch_url:
            raise LinkExtractionError(LinkExtractionFailureReason.UNUSABLE_CONTENT)
        return fetch_url
    safe_fetch_url = sanitize_url(fetch_url)
    safe_browser_url = sanitize_url(browser_url)

    async def fetch_and_convert(content: str, base_url: str) -> str | None:
        """Cleans HTML or parses JSON and converts it to Markdown."""
        if _is_reddit_rss_url(base_url):
            markdown = _parse_reddit_rss_to_markdown(content)
            if markdown:
                return markdown

        if _is_reddit_json_url(base_url):
            try:
                reddit_data = json.loads(content)
                return _parse_reddit_json_to_markdown(reddit_data)
            except (json.JSONDecodeError, IndexError, KeyError, TypeError) as error:
                logger.error(
                    "Failed to parse Reddit JSON for %s (%s)",
                    sanitize_url(base_url),
                    type(error).__name__,
                )
                # Fallback to treating it as regular HTML if parsing fails
                pass

        if "arxivmd.org" in base_url:
            return content

        if _is_reddit_url(base_url) and not _is_reddit_structured_url(base_url):
            content = await asyncio.to_thread(_prepare_reddit_html_for_markdown, content)

        cleaned_html = await asyncio.to_thread(clean_html, content)
        markdown = await asyncio.to_thread(convert_to_markdown, cleaned_html, base_url=base_url)
        return markdown if len(markdown) >= MIN_MARKDOWN_LENGTH else None

    decision = FetchDecision.STOP
    attempt_error: FetchAttemptError | None = None
    async with AsyncSession() as session:
        for attempt in range(MAX_DIRECT_ATTEMPTS):
            try:
                html = await fetch_http_once(session, fetch_url)
                markdown = await fetch_and_convert(html, fetch_url)
                if markdown:
                    return markdown
                decision = FetchDecision.BROWSER_FALLBACK
            except FetchAttemptError as error:
                attempt_error = error
                decision = error.decision
                logger.warning(
                    "Direct fetch attempt %s/%s failed for %s (%s)",
                    attempt + 1,
                    MAX_DIRECT_ATTEMPTS,
                    safe_fetch_url,
                    decision.value,
                )
            except Exception as error:
                decision = FetchDecision.BROWSER_FALLBACK
                logger.warning(
                    "Direct content processing failed for %s (%s)",
                    safe_fetch_url,
                    type(error).__name__,
                )

        if decision is FetchDecision.STOP:
            if attempt_error is not None and attempt_error.status_code is not None:
                raise LinkExtractionError(
                    LinkExtractionFailureReason.HTTP_REJECTED,
                    attempt_error.status_code,
                )
            raise LinkExtractionError(LinkExtractionFailureReason.FETCH_FAILED)

        if decision is FetchDecision.RETRY:
            proxies_to_try = min(MAX_PROXY_ATTEMPTS, len(proxy_manager.proxies))
            logger.info(
                "Transient direct fetch failure; trying %s proxies for %s",
                proxies_to_try,
                safe_fetch_url,
            )
            for attempt in range(proxies_to_try):
                proxy_dict = await proxy_manager.get_proxy()
                if not proxy_dict:
                    continue
                proxy_url = proxy_dict.get("https", proxy_dict.get("http"))
                try:
                    html = await fetch_http_once(session, fetch_url, proxy=proxy_url)
                    markdown = await fetch_and_convert(html, fetch_url)
                    if markdown:
                        return markdown
                    decision = FetchDecision.BROWSER_FALLBACK
                except FetchAttemptError as error:
                    attempt_error = error
                    decision = error.decision
                    logger.warning(
                        "Proxy attempt %s/%s failed for %s (%s)",
                        attempt + 1,
                        proxies_to_try,
                        safe_fetch_url,
                        decision.value,
                    )
                except Exception as error:
                    decision = FetchDecision.BROWSER_FALLBACK
                    logger.warning(
                        "Proxy content processing failed for %s (%s)",
                        safe_fetch_url,
                        type(error).__name__,
                    )

                if decision is FetchDecision.STOP:
                    if attempt_error is not None and attempt_error.status_code is not None:
                        raise LinkExtractionError(
                            LinkExtractionFailureReason.HTTP_REJECTED,
                            attempt_error.status_code,
                        )
                    raise LinkExtractionError(LinkExtractionFailureReason.FETCH_FAILED)
                if decision is FetchDecision.BROWSER_FALLBACK:
                    break

        logger.info("Falling back to headless browser for %s", safe_browser_url)
        try:
            html = await browser_fetch_manager.fetch(browser_url)
        except LinkExtractionError:
            raise
        except Exception as error:
            logger.warning(
                "Browser fallback failed for %s (%s)",
                safe_browser_url,
                type(error).__name__,
            )
            raise LinkExtractionError(LinkExtractionFailureReason.BROWSER_FAILED) from error

        try:
            markdown = await fetch_and_convert(html, browser_url)
            if markdown:
                return markdown
            raise LinkExtractionError(LinkExtractionFailureReason.UNUSABLE_CONTENT)
        except LinkExtractionError:
            raise
        except Exception as error:
            logger.warning(
                "Browser content processing failed for %s (%s)",
                safe_browser_url,
                type(error).__name__,
            )
            raise LinkExtractionError(LinkExtractionFailureReason.FETCH_FAILED) from error

    raise LinkExtractionError(LinkExtractionFailureReason.FETCH_FAILED)
