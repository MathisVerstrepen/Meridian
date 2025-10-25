import asyncio
import logging
import random

from curl_cffi.requests import AsyncSession

logger = logging.getLogger("uvicorn.error")

PROXIES_FILE_PATH = "proxies.txt"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",  # noqa: E501
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",  # noqa: E501
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",  # noqa: E501
]


def get_browser_headers(url: str) -> dict[str, str]:
    """Returns a set of common browser headers with some randomization."""
    from urllib.parse import urlparse

    parsed_url = urlparse(url)
    referer = random.choice(
        [
            f"{parsed_url.scheme}://{parsed_url.netloc}/",
            "https://www.google.com/",
            "https://www.bing.com/",
            "https://www.reddit.com/",
        ]
    )

    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",  # noqa: E501
        "Accept-Language": random.choice(
            [
                "en-US,en;q=0.9",
                "en-GB,en;q=0.9",
                "en-US,en;q=0.8,fr;q=0.6",
                "en-US,en;q=0.9,es;q=0.8",
                "en-US,en;q=0.9,de;q=0.7",
            ]
        ),
        "Referer": referer,
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


class ProxyManager:
    """
    Manages loading, formatting, and rotating proxies from configuration.
    """

    def __init__(self):
        self.proxies: list[dict[str, str]] = []
        self.current_index = 0
        self.lock = asyncio.Lock()

    def _load_from_file(self, file_path: str, proxy_type: str):
        """Loads proxies from a text file (IP:PORT:USER:PASS)."""

        # Check if file exists and is readable
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                pass
        except Exception as e:
            logger.warning(f"No proxy file found at '{file_path}': {e}")
            return

        try:
            n_proxies = 0
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split(":")
                    if len(parts) != 4:
                        logger.warning(f"Skipping malformed proxy line: {line}")
                        continue

                    ip, port, user, password = parts
                    proxy_url = f"{proxy_type}://{user}:{password}@{ip}:{port}"
                    self.proxies.append({"http": proxy_url, "https": proxy_url})
                    n_proxies += 1

            logger.info(f"Loaded {n_proxies} proxies from {file_path}")
        except FileNotFoundError:
            logger.error(
                f"Proxy file not found at '{file_path}'. Please check the path in your config.yaml."
            )
        except Exception as e:
            logger.error(f"Failed to read or parse proxy file: {e}")

    async def get_proxy(self) -> dict[str, str] | None:
        """
        Returns the next proxy in the list in a thread-safe, round-robin fashion.
        Returns None if no proxies are loaded.
        """
        if not self.proxies:
            return None

        async with self.lock:
            proxy: dict[str, str] = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy


# Global session for connection reuse and cookie persistence
proxy_manager: ProxyManager = ProxyManager()
proxy_manager._load_from_file(PROXIES_FILE_PATH, "socks5h")
_session = None


async def get_session() -> AsyncSession:
    """
    Returns a persistent async session with browser-like configuration.
    """
    global _session
    if _session is None:
        _session = AsyncSession()
    return _session  # type: ignore
