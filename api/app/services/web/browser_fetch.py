import asyncio
import os
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from services.web.fetch_errors import BrowserFetchError, LinkExtractionFailureReason

SERVICE_URL_ENV = "LINK_EXTRACTION_BROWSER_SERVICE_URL"
SERVICE_TOKEN_ENV = "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN"
ALLOWED_RESPONSE_STATUSES = {200, 429, 502, 503, 504}


class BrowserFetchManager:
    """Lazy authenticated no-retry client for the isolated browser service."""

    def __init__(
        self,
        *,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
        env_getter: Callable[[str, str], str] = os.getenv,
        uuid_factory: Callable[[], Any] = uuid4,
    ) -> None:
        self._client_factory = client_factory
        self._env_getter = env_getter
        self._uuid_factory = uuid_factory
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._base_url: str | None = None
        self._token: str | None = None
        self._in_flight: set[asyncio.Task[Any]] = set()
        self._closed = False

    def _load_configuration(self) -> tuple[str, str]:
        raw_url = self._env_getter(SERVICE_URL_ENV, "").strip()
        token = self._env_getter(SERVICE_TOKEN_ENV, "")
        try:
            parsed = urlsplit(raw_url)
            valid_url = (
                parsed.scheme.lower() in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
            )
            if not valid_url:
                raise ValueError
            base_url = urlunsplit(
                (parsed.scheme.lower(), parsed.netloc, parsed.path.rstrip("/"), "", "")
            )
        except (TypeError, ValueError):
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED) from None
        if (
            len(token) < 32
            or any(not "!" <= character <= "~" for character in token)
            or token.lower()
            in {
                "change-me",
                "replace-me",
                "example",
            }
        ):
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
        return base_url, token

    async def _get_client(self) -> tuple[httpx.AsyncClient, str, str]:
        async with self._lock:
            if self._closed:
                raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
            if self._client is None:
                self._base_url, self._token = self._load_configuration()
                self._client = self._client_factory(
                    http2=False,
                    trust_env=False,
                    timeout=httpx.Timeout(95.0, connect=5.0, write=5.0, pool=5.0),
                )
            assert self._base_url is not None and self._token is not None
            return self._client, self._base_url, self._token

    async def fetch(self, url: str) -> str:
        client, base_url, token = await self._get_client()
        request_id = str(self._uuid_factory())
        async with self._lock:
            if self._closed:
                raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
            operation = asyncio.create_task(
                self._perform_fetch(client, base_url, token, request_id, url)
            )
            self._in_flight.add(operation)
            operation.add_done_callback(self._in_flight.discard)
        try:
            return await operation
        except asyncio.CancelledError:
            operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            raise
        finally:
            self._in_flight.discard(operation)

    async def _perform_fetch(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        token: str,
        request_id: str,
        url: str,
    ) -> str:
        try:
            async with asyncio.timeout(95.0):
                response = await client.post(
                    f"{base_url}/v1/fetch",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"request_id": request_id, "url": url},
                )
            return self._decode_response(response, request_id)
        except asyncio.CancelledError:
            raise
        except BrowserFetchError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise BrowserFetchError(LinkExtractionFailureReason.CONNECTIVITY_EXHAUSTED) from None
        except Exception:
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED) from None

    @staticmethod
    def _decode_response(response: httpx.Response, request_id: str) -> str:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
        if (
            response.status_code not in ALLOWED_RESPONSE_STATUSES
            or content_type != "application/json"
        ):
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
        try:
            payload = response.json()
        except Exception:
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED) from None
        if not isinstance(payload, dict) or payload.get("request_id") != request_id:
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
        if response.status_code == 200:
            html = payload.get("html")
            if set(payload) != {"request_id", "html"} or not isinstance(html, str):
                raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
            return html
        error = payload.get("error")
        if set(payload) != {"request_id", "error"} or not isinstance(error, dict):
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
        if set(error) != {"reason", "status_code"}:
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
        try:
            reason = LinkExtractionFailureReason(error.get("reason"))
        except (TypeError, ValueError):
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED) from None
        status_code = error.get("status_code")
        if status_code is not None and (
            not isinstance(status_code, int)
            or isinstance(status_code, bool)
            or not 400 <= status_code <= 599
        ):
            raise BrowserFetchError(LinkExtractionFailureReason.BROWSER_FAILED)
        return BrowserFetchManager._raise_typed(reason, status_code)

    @staticmethod
    def _raise_typed(reason: LinkExtractionFailureReason, status_code: int | None) -> str:
        raise BrowserFetchError(reason, status_code)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            client = self._client
            self._client = None
            tasks = tuple(self._in_flight)
            for task in tasks:
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if client is not None:
            await client.aclose()


browser_fetch_manager = BrowserFetchManager()
