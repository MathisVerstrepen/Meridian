import asyncio
import logging
from typing import Any, Mapping

from playwright._impl._errors import TargetClosedError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .diagnostics import CHALLENGE_BODY_SCAN_LENGTH as _CHALLENGE_BODY_SCAN_LENGTH
from .diagnostics import has_challenge_marker
from .diagnostics import is_browser_challenge as _is_browser_challenge
from .diagnostics import response_diagnostics
from .models import BrowserFetchError, FailureReason

logger = logging.getLogger("uvicorn.error")
CHALLENGE_BODY_SCAN_LENGTH = _CHALLENGE_BODY_SCAN_LENGTH
CHALLENGE_TOTAL_TIMEOUT_SECONDS = 15
CHALLENGE_OPERATION_TIMEOUT_MS = 5000
CHALLENGE_CLEAR_CONDITION = """() => {
    const text = (document.body?.innerText || '').toLowerCase();
    return !document.querySelector('#cmsg') &&
        !text.includes('please enable js and disable any ad blocker');
}"""


class _ChallengeUnresolved(Exception):
    pass


def is_browser_challenge(
    status_code: int | None,
    headers: Mapping[object, object] | None,
    body: object,
) -> bool:
    return _is_browser_challenge(status_code, headers, body)


async def resolve_browser_challenge(
    page: Any,
    initial_response: Any,
    initial_body: str,
    initial_url: str,
    initial_headers: Mapping[object, object],
    *,
    proxy_enabled: bool,
) -> str:
    latest_status = int(initial_response.status)
    latest_body = initial_body
    latest_url = initial_url
    latest_headers = initial_headers
    phase = "initial"
    terminal_reason = FailureReason.CHALLENGE_UNRESOLVED
    try:
        async with asyncio.timeout(CHALLENGE_TOTAL_TIMEOUT_SECONDS):
            deadline = asyncio.get_running_loop().time() + CHALLENGE_TOTAL_TIMEOUT_SECONDS
            _record_state(proxy_enabled, phase, "pending")
            phase = "wait"
            _record_state(proxy_enabled, phase, "pending")
            await _wait_for_clear(page, deadline)
            latest_url, latest_body = await _read_page_state(page)
            accepted = _validated_content(latest_body)
            if accepted is not None:
                _record_state(proxy_enabled, phase, "cleared_after_wait")
                return accepted

            phase = "reload"
            _record_state(proxy_enabled, phase, "pending")
            latest_response = await page.reload(
                timeout=remaining_timeout_ms(deadline), wait_until="domcontentloaded"
            )
            if latest_response is None:
                raise _ChallengeUnresolved
            latest_status = int(latest_response.status)
            latest_headers = await response_headers(latest_response)
            latest_url, latest_body = await _read_page_state(page)
            if is_browser_challenge(latest_status, latest_headers, latest_body):
                phase = "final"
                _record_state(proxy_enabled, phase, "pending")
                await _wait_for_clear(page, deadline)
                latest_url, latest_body = await _read_page_state(page)
            accepted = _validated_content(latest_body)
            if accepted is None:
                if not has_challenge_marker(latest_body):
                    raise BrowserFetchError(FailureReason.UNUSABLE_CONTENT)
                raise _ChallengeUnresolved
            _record_state(proxy_enabled, "final", "cleared_after_reload")
            return accepted
    except (_ChallengeUnresolved, TimeoutError):
        pass
    except BrowserFetchError as error:
        terminal_reason = error.reason
    except TargetClosedError:
        raise
    except Exception:
        pass
    # Diagnostics use state captured inside the original deadline. Never perform
    # another renderer read after the challenge budget expires.
    logger.warning(
        "Browser challenge unresolved: %s",
        response_diagnostics(
            requested_url=initial_url,
            status_code=latest_status,
            decision="stop",
            response_url=latest_url,
            headers=latest_headers,
            body=latest_body,
        ),
    )
    raise BrowserFetchError(terminal_reason)


def _record_state(proxy_enabled: bool, phase: str, outcome: str) -> None:
    logger.info(
        "Browser challenge state: proxy_enabled=%s phase=%s outcome=%s",
        proxy_enabled,
        phase,
        outcome,
    )


def _validated_content(body: str) -> str | None:
    if has_challenge_marker(body):
        return None
    return body if body.strip() and len(body) >= 2000 else None


async def _read_page_state(page: Any) -> tuple[str, str]:
    try:
        return str(page.url), str(await page.content())
    except TargetClosedError:
        raise
    except Exception:
        raise BrowserFetchError(FailureReason.BROWSER_FAILED) from None


async def _wait_for_clear(page: Any, deadline: float) -> None:
    try:
        await page.wait_for_function(
            CHALLENGE_CLEAR_CONDITION, timeout=remaining_timeout_ms(deadline)
        )
    except PlaywrightTimeoutError:
        pass


def remaining_timeout_ms(deadline: float) -> int:
    remaining = int((deadline - asyncio.get_running_loop().time()) * 1000)
    if remaining <= 0:
        raise TimeoutError
    return min(CHALLENGE_OPERATION_TIMEOUT_MS, remaining)


async def safe_page_content(page: Any) -> str:
    try:
        return str(await page.content())
    except TargetClosedError:
        raise
    except Exception:
        return ""


async def response_headers(response: Any) -> Mapping[object, object]:
    if response is None:
        return {}
    try:
        return dict(await response.all_headers())
    except TargetClosedError:
        raise
    except Exception:
        return {}
