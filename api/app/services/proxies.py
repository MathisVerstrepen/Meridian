import asyncio
import logging

from curl_cffi.requests import AsyncSession

logger = logging.getLogger("uvicorn.error")

PROXIES_FILE_PATH = "proxies.txt"


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
