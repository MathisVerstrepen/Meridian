import asyncio
import logging
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from patchright.async_api import async_playwright

from services.proxies import proxy_manager, get_browser_headers

logger = logging.getLogger("uvicorn.error")

MIN_MARKDOWN_LENGTH = 500
MIN_HTML_LENGTH = 2000


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
    return markdown_text


async def _attempt_fetch(session: AsyncSession, url: str, proxy: str | None = None) -> str:
    """
    Performs a single, robust fetch attempt for a URL.

    Args:
        session: The AsyncSession to use.
        url: The URL to fetch.
        proxy: Optional proxy URL.

    Returns:
        The HTML content as a string.

    Raises:
        Exception: If the fetch fails, is blocked, or content is invalid.
    """
    # Use a more recent browser profile for impersonation
    impersonate_version = "chrome120"
    headers = get_browser_headers(url)

    try:
        response = await session.get(
            url,
            headers=headers,
            impersonate=impersonate_version,
            proxy=proxy,
            timeout=20,
            allow_redirects=True,
        )

        response.raise_for_status()  # Raises for 4xx/5xx

        html = response.text

        if len(html) < MIN_HTML_LENGTH:
            raise Exception(f"Content too short for {url} (len: {len(html)})")

        return html

    except Exception as e:
        proxy_info = f"via proxy {proxy.split('@')[-1]}" if proxy else "directly"
        logger.debug(f"Fetch attempt failed for {url} {proxy_info}: {e}")
        raise Exception(f"Failed to fetch {url} {proxy_info}: {e}") from e


async def _attempt_browser_fetch(url: str) -> str:
    """
    Fallback fetch using a headless browser to handle JavaScript-heavy or anti-bot sites.
    Requires `playwright` library: pip install playwright && playwright install
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="./.playwright_data",
            channel="chrome",
            headless=True,
            no_viewport=True,
        )
        page = await browser.new_page()
        try:
            response = await page.goto(url, timeout=15000, wait_until="networkidle")
            if response.status >= 400:
                raise Exception(f"Browser fetch failed with status {response.status} for {url}")

            html = await page.content()

            if len(html) < MIN_HTML_LENGTH:
                raise Exception(f"Content too short in browser for {url}")

            return html
        except Exception as e:
            logger.debug(f"Browser fetch failed for {url}: {e}")
            raise
        finally:
            await browser.close()


def _preprocess_url(url: str) -> str:
    """
    Preprocesses the URL to ensure it is well-formed.
    """
    # Add /.json for Reddit URLs to get cleaner content
    if "www.reddit.com" in url:
        url += ".json"

    # Use https://arxivmd.org/ for arXiv links to get Markdown directly
    if "arxiv.org" in url:
        parts = url.split("/")
        paper_id = parts[-1] if parts[-1] else parts[-2]
        url = f"https://arxivmd.org/format/{paper_id}"

    if not url.startswith("http") and not url.startswith("https"):
        url = "https://" + url
    return url


async def url_to_markdown(url: str) -> str | None:
    """
    Fetches a URL with a robust retry and fallback strategy, then converts its
    main content to Markdown.

    Strategy:
    1. Tries a direct request with retries and exponential backoff.
    2. If direct fails, falls back to using proxies.
    3. Tries multiple proxies from the pool.
    """
    MAX_DIRECT_ATTEMPTS = 1
    MAX_PROXY_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 2

    url = _preprocess_url(url)

    async def fetch_and_convert(html: str, base_url: str) -> str | None:
        """Cleans HTML and converts it to Markdown."""
        if "www.reddit.com" in base_url:
            return html

        if "arxivmd.org" in base_url:
            return html

        cleaned_html = clean_html(html)
        markdown = convert_to_markdown(cleaned_html, base_url=base_url)
        return markdown if len(markdown) >= MIN_MARKDOWN_LENGTH else None

    async with AsyncSession() as session:
        # --- Stage 1: Direct Fetch Attempts ---
        for attempt in range(MAX_DIRECT_ATTEMPTS):
            try:
                html = await _attempt_fetch(session, url)
                markdown = await fetch_and_convert(html, url)
                if markdown:
                    return markdown
            except Exception as e:
                logger.warning(
                    f"Direct fetch attempt {attempt + 1}/{MAX_DIRECT_ATTEMPTS} failed for {url}: {e}"
                )
                if attempt < MAX_DIRECT_ATTEMPTS - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * (2**attempt))

        # --- Stage 2: Fallback to Proxies ---
        if not proxy_manager.proxies:
            logger.warning("No proxies available, cannot perform fallback fetch.")
            return None

        logger.info(f"Direct fetch failed. Falling back to proxies for {url}")

        proxies_to_try = min(MAX_PROXY_ATTEMPTS, len(proxy_manager.proxies))
        for i in range(proxies_to_try):
            proxy_dict = await proxy_manager.get_proxy()
            if not proxy_dict:
                continue

            proxy_url = proxy_dict.get("https", proxy_dict.get("http"))

            try:
                html = await _attempt_fetch(session, url, proxy=proxy_url)
                markdown = await fetch_and_convert(html, url)
                if markdown:
                    return markdown
            except Exception as e:
                logger.warning(f"Proxy attempt {i + 1}/{proxies_to_try} failed: {e}")

        # --- Stage 3: Fallback to Headless Browser ---
        logger.info(f"Proxy fetch failed. Falling back to headless browser for {url}")
        try:
            html = await _attempt_browser_fetch(url)
            markdown = await fetch_and_convert(html, url)
            if markdown:
                return markdown
        except Exception as e:
            logger.warning(f"Browser fallback failed for {url}: {e}")

        logger.error(f"All fetch attempts (direct, proxy, browser) failed for {url}")
        return None
