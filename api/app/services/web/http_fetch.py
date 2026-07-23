import logging
import re
from enum import Enum
from typing import Mapping
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import sentry_sdk
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import ConnectionError, ProxyError, RequestException, Timeout
from services.web.reddit import _is_reddit_structured_url

logger = logging.getLogger("uvicorn.error")

MIN_HTML_LENGTH = 2000
CHALLENGE_BODY_SCAN_LENGTH = 8192
MAX_HEADER_COUNT = 12
MAX_HEADER_VALUE_LENGTH = 256
MAX_HEADERS_TOTAL_LENGTH = 2048

_ALLOWED_HEADERS = {
    "content-type",
    "server",
    "via",
    "retry-after",
    "location",
    "x-cache",
    "cf-ray",
    "cf-cache-status",
    "x-amz-cf-id",
    "x-request-id",
}
_SECRET_NAME = r"(?:api[_-]?key|key|password|passwd|session|secret|token|auth)"
_ASSIGNMENT_RE = re.compile(rf"(?i)\b({_SECRET_NAME})\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/]+=*")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9._~-]{24,}\b")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_WHITESPACE_RE = re.compile(r"\s+")
_PATH_ASSIGNMENT_RE = re.compile(rf"(?i)(?:^|[-_.]){_SECRET_NAME}(?:[-_.:=]|$)")


class FetchDecision(str, Enum):
    RETRY = "retry"
    BROWSER_FALLBACK = "browser_fallback"
    STOP = "stop"


class FetchAttemptError(Exception):
    def __init__(
        self,
        decision: FetchDecision,
        reason: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(reason)
        self.decision = decision
        self.reason = reason
        self.status_code = status_code


def _is_token_like(value: str) -> bool:
    if _JWT_RE.fullmatch(value):
        return True
    if len(value) < 24 or not re.fullmatch(r"[A-Za-z0-9._~-]+", value):
        return False
    character_classes = sum(
        bool(re.search(pattern, value)) for pattern in (r"[a-z]", r"[A-Z]", r"\d")
    )
    return character_classes >= 2 or bool(re.fullmatch(r"[A-Fa-f0-9]+", value))


def _sanitize_path(path: str) -> str:
    sanitized_segments = []
    for raw_segment in path.split("/"):
        segment = unquote(raw_segment)
        if _PATH_ASSIGNMENT_RE.search(segment) or _is_token_like(segment):
            sanitized_segments.append("[redacted]")
        else:
            sanitized_segments.append(quote(segment, safe="!$&'()*+,;=:@-._~"))
    return "/".join(sanitized_segments)


def sanitize_url(url: object) -> str:
    try:
        parsed = urlsplit(str(url))
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").rstrip(".").lower()
        if not scheme or not hostname:
            return "[invalid-url]"
        host = f"[{hostname}]" if ":" in hostname else hostname
        try:
            port = parsed.port
        except ValueError:
            return "[invalid-url]"
        netloc = f"{host}:{port}" if port is not None else host
        return urlunsplit((scheme, netloc, _sanitize_path(parsed.path), "", ""))
    except (TypeError, ValueError, UnicodeError):
        return "[invalid-url]"


def _sanitize_header_value(body: object) -> str:
    source = str(body)[:2048]
    source = _CONTROL_RE.sub(" ", source)
    source = _WHITESPACE_RE.sub(" ", source).strip()
    source = _BEARER_RE.sub("Bearer [redacted]", source)
    source = _JWT_RE.sub("[redacted]", source)
    source = _ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[redacted]", source)
    source = _LONG_TOKEN_RE.sub(
        lambda match: ("[redacted]" if _is_token_like(match.group(0)) else match.group(0)),
        source,
    )
    return source[:256]


def sanitize_headers(headers: Mapping[object, object] | None) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    total_length = 0
    if not headers:
        return sanitized

    for raw_name, raw_value in headers.items():
        name = str(raw_name).lower()
        if name not in _ALLOWED_HEADERS or len(sanitized) >= MAX_HEADER_COUNT:
            continue
        value = str(raw_value)
        if name == "location":
            value = sanitize_url(value)
        else:
            value = _sanitize_header_value(value)
        value = value[:MAX_HEADER_VALUE_LENGTH]
        remaining = MAX_HEADERS_TOTAL_LENGTH - total_length - len(name)
        if remaining <= 0:
            break
        value = value[:remaining]
        sanitized[name] = value
        total_length += len(name) + len(value)
    return sanitized


def response_diagnostics(
    *,
    status_code: int | None,
    decision: FetchDecision,
    response_url: object,
    headers: Mapping[object, object] | None,
    body: object,
    requested_url: object | None = None,
) -> dict[str, object]:
    return {
        "status": status_code,
        "decision": decision.value,
        "url": sanitize_url(response_url),
        "headers": sanitize_headers(headers),
        "body_markers": _body_markers(
            requested_url if requested_url is not None else response_url,
            response_url,
            status_code,
            headers,
            body,
        ),
    }


def _body_markers(
    requested_url: object,
    response_url: object,
    status_code: int | None,
    headers: Mapping[object, object] | None,
    body: object,
) -> list[str]:
    del requested_url, response_url
    if is_browser_challenge(status_code, headers, body):
        return ["browser_challenge"]
    return []


def is_browser_challenge(
    status_code: int | None,
    headers: Mapping[object, object] | None,
    body: object,
) -> bool:
    if status_code not in {401, 403}:
        return False
    sample = str(body)[:CHALLENGE_BODY_SCAN_LENGTH].lower()
    if "please enable js and disable any ad blocker" in sample:
        return True
    lambda_response = any(
        str(name).lower() == "x-cache" and "lambdageneratedresponse" in str(value).lower()
        for name, value in (headers or {}).items()
    )
    cmsg_marker = any(marker in sample for marker in ('id="cmsg"', "id='cmsg'", "#cmsg"))
    return lambda_response and cmsg_marker


def classify_status(
    status_code: int,
    headers: Mapping[object, object] | None,
    body: object,
) -> FetchDecision:
    if status_code == 429 or 500 <= status_code <= 599:
        return FetchDecision.RETRY
    if status_code == 403:
        return FetchDecision.BROWSER_FALLBACK
    if status_code == 401 and is_browser_challenge(status_code, headers, body):
        return FetchDecision.BROWSER_FALLBACK
    return FetchDecision.STOP


def validate_content(content: object, url: str) -> str:
    text = str(content)
    if not text.strip():
        raise FetchAttemptError(FetchDecision.BROWSER_FALLBACK, "empty response content")
    if len(text) < MIN_HTML_LENGTH and not _is_reddit_structured_url(url):
        raise FetchAttemptError(FetchDecision.BROWSER_FALLBACK, "response content too short")
    return text


def _log_response_failure(
    *,
    status_code: int | None,
    decision: FetchDecision,
    response_url: object,
    headers: Mapping[object, object] | None,
    body: object,
    requested_url: object,
) -> None:
    diagnostics = response_diagnostics(
        status_code=status_code,
        decision=decision,
        response_url=response_url,
        headers=headers,
        body=body,
        requested_url=requested_url,
    )
    logger.warning("HTTP fetch rejected response: %s", diagnostics)


async def fetch_http_once(session: AsyncSession, url: str, proxy: str | None = None) -> str:
    op = "web.link_extraction.proxy_fetch" if proxy else "web.link_extraction.direct_fetch"
    safe_url = sanitize_url(url)
    with sentry_sdk.start_span(op=op, description="Fetch URL with curl-cffi") as span:
        span.set_data("url", safe_url)
        span.set_data("proxy_enabled", proxy is not None)
        try:
            response = await session.get(
                url,
                impersonate="chrome120",  # type: ignore
                proxy=proxy,
                timeout=20,
                allow_redirects=True,
            )
        except (Timeout, ConnectionError, ProxyError) as error:
            span.set_status("internal_error")
            logger.warning(
                "Transient HTTP fetch failure for %s (%s)",
                safe_url,
                type(error).__name__,
            )
            raise FetchAttemptError(FetchDecision.RETRY, "transient network failure") from error
        except RequestException as error:
            span.set_status("internal_error")
            logger.warning(
                "Permanent HTTP fetch failure for %s (%s)",
                safe_url,
                type(error).__name__,
            )
            raise FetchAttemptError(FetchDecision.STOP, "request failure") from error
        except Exception as error:
            span.set_status("internal_error")
            logger.warning(
                "Unexpected HTTP fetch failure for %s (%s)",
                safe_url,
                type(error).__name__,
            )
            raise FetchAttemptError(FetchDecision.STOP, "unexpected request failure") from error

        try:
            status_code = int(response.status_code)
            response_url = getattr(response, "url", None) or url
            response_headers = getattr(response, "headers", None)
            body = str(response.text)
        except Exception as error:
            span.set_status("internal_error")
            logger.warning("Invalid HTTP response for %s (%s)", safe_url, type(error).__name__)
            raise FetchAttemptError(FetchDecision.STOP, "invalid HTTP response") from error
        if status_code >= 400:
            decision = classify_status(status_code, response_headers, body)
            _log_response_failure(
                status_code=status_code,
                decision=decision,
                response_url=response_url,
                headers=response_headers,
                body=body,
                requested_url=url,
            )
            span.set_status("internal_error")
            raise FetchAttemptError(decision, "HTTP response rejected", status_code)

        try:
            return validate_content(body, url)
        except FetchAttemptError as error:
            _log_response_failure(
                status_code=status_code,
                decision=error.decision,
                response_url=response_url,
                headers=response_headers,
                body=body,
                requested_url=url,
            )
            span.set_status("internal_error")
            raise
