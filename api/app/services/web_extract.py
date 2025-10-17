import asyncio
import logging
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from services.proxies import proxy_manager, get_browser_headers, make_proxy_request

logger = logging.getLogger("uvicorn.error")


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
        convert_images=True,  # Try to convert images with alt text
        strip=["a"],  # You can strip links but keep the text
        autolinks=False,  # Don't automatically convert URLs to links
        base_url=base_url,  # Helps resolve relative image/link paths
    )
    return markdown_text


async def fetch_fast(session: AsyncSession, url: str) -> tuple[str | None, bool]:
    """
    Attempts to fetch a URL quickly using curl_cffi.

    Returns:
        A tuple of (html_content, needs_fallback).
        `needs_fallback` is True if the request was likely blocked.
    """
    try:
        # impersonate="chrome110" handles TLS fingerprinting
        response = await session.get(
            url, headers=get_browser_headers(), impersonate="chrome110", timeout=15
        )

        response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

        html = response.text

        # Basic check for common block pages/CAPTCHAs
        if "captcha" in html.lower() or "verify you are human" in html.lower():
            logger.warning(f"Blocked by CAPTCHA for {url}")
            return None, True

        if len(html) < 100:
            logger.warning(f"Fetched content too short for {url}")
            return None, True

        return html, False

    except Exception as e:
        logger.warning(f"Fast fetch failed for {url}: {e}")
        return None, True


async def url_to_markdown(url: str) -> str | None:
    """
    Fetches a URL and converts its main content to Markdown.
    """

    async def fetch_and_convert(html: str, base_url: str) -> str | None:
        """
        Cleans HTML and converts it to Markdown.
        """
        cleaned_html = clean_html(html)
        markdown = convert_to_markdown(cleaned_html, base_url=base_url)
        return markdown if len(markdown) >= 50 else None

    async with AsyncSession() as session:
        html, needs_fallback = await fetch_fast(session, url)
        if not needs_fallback and html:
            markdown = await fetch_and_convert(html, url)
            if markdown:
                return markdown

        # Fallback: Use proxy to fetch the page
        try:
            if len(proxy_manager.proxies) == 0:
                logger.warning("No proxies available for fallback fetch.")
                return None
            logger.info(f"Attempting fallback fetch for {url} via proxy")
            response = await make_proxy_request(proxy_manager, url)
            response.raise_for_status()
            html = response.text

            markdown = await fetch_and_convert(html, url)
            if markdown:
                return markdown

            logger.error(f"Fallback fetch resulted in too short content for {url}")
        except Exception as e:
            logger.error(f"Fallback fetch failed for {url}: {e}")

    return None


if __name__ == "__main__":

    async def main():
        urls = [
            "https://en.wikipedia.org/wiki/Prime_Minister_of_France",
            "https://www.cnbc.com/2025/10/10/frances-macron-reappoints-former-prime-minister-lecornu-as-pm.html",
            "https://time.com/7315856/sebastien-lecornu-prime-minister-france-macron-bayrou-government-collapse-protests/",
            "https://www.pbs.org/newshour/world/frances-new-prime-minister-resigns-hours-after-naming-government-plunging-france-further-into-political-chaos",
        ]

        async with AsyncSession() as session:
            tasks = [fetch_fast(session, url) for url in urls]
            results = await asyncio.gather(*tasks)

            for url, (html, needs_fallback) in zip(urls, results):
                if needs_fallback:
                    print(f"URL {url} needs fallback handling.")
                else:
                    # Convert html to markdown
                    cleaned_html = clean_html(html)
                    markdown = convert_to_markdown(cleaned_html, base_url=url)
                    print(f"Markdown for {url}:\n{markdown[:1000]}...\n")

    asyncio.run(main())
