import re
from typing import Mapping
from urllib.parse import quote, unquote, urlsplit, urlunsplit

BROWSER_CHALLENGE_MARKER = "browser_challenge"
CHALLENGE_TEXT = "please enable js and disable any ad blocker"
CHALLENGE_BODY_SCAN_LENGTH = 8192
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
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_HEADER_SECRET_RE = re.compile(
    r"(?i)(bearer\s+\S+|"
    r"(?:api[_-]?key|password|passwd|session|secret|token|auth)\s*[:=]\s*\S+|"
    r"\b[A-Za-z0-9._~-]{32,}\b)"
)
_SECRET_SEGMENT_RE = re.compile(
    r"(?i)(?:^|[-_.])(?:api[_-]?key|password|passwd|session|secret|token|auth)(?:[-_.:=]|$)"
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")


def _is_token_like(value: str) -> bool:
    if _JWT_RE.fullmatch(value):
        return True
    if len(value) < 24 or not re.fullmatch(r"[A-Za-z0-9._~-]+", value):
        return False
    character_classes = sum(
        bool(re.search(pattern, value)) for pattern in (r"[a-z]", r"[A-Z]", r"\d")
    )
    return character_classes >= 2 or bool(re.fullmatch(r"[A-Fa-f0-9]+", value))


def sanitize_url(url: object) -> str:
    try:
        parsed = urlsplit(str(url))
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            return "[invalid-url]"
        rendered_host = f"[{host}]" if ":" in host else host
        port = parsed.port
        netloc = f"{rendered_host}:{port}" if port is not None else rendered_host
        segments = []
        for raw in parsed.path.split("/"):
            value = unquote(raw)
            segments.append(
                "[redacted]"
                if _SECRET_SEGMENT_RE.search(value) or _is_token_like(value) or len(value) >= 64
                else quote(value, safe="!$&'()*+,;=:@-._~")
            )
        return urlunsplit((parsed.scheme.lower(), netloc, "/".join(segments), "", ""))
    except (TypeError, ValueError, UnicodeError):
        return "[invalid-url]"


def sanitize_headers(headers: Mapping[object, object] | None) -> dict[str, str]:
    output: dict[str, str] = {}
    total = 0
    for raw_name, raw_value in (headers or {}).items():
        name = str(raw_name).lower()
        if name not in _ALLOWED_HEADERS or len(output) >= 12:
            continue
        value = sanitize_url(raw_value) if name == "location" else str(raw_value)
        value = _CONTROL_RE.sub(" ", value)[:256]
        if name != "location":
            value = _HEADER_SECRET_RE.sub("[redacted]", value)
        remaining = 2048 - total - len(name)
        if remaining <= 0:
            break
        output[name] = value[:remaining]
        total += len(name) + len(output[name])
    return output


def has_lambda_generated_response(headers: Mapping[object, object]) -> bool:
    return any(
        str(name).lower() == "x-cache" and "lambdageneratedresponse" in str(value).lower()
        for name, value in headers.items()
    )


def has_challenge_marker(body: str) -> bool:
    sample = body[:CHALLENGE_BODY_SCAN_LENGTH].lower()
    return CHALLENGE_TEXT in sample or any(
        marker in sample for marker in ('id="cmsg"', "id='cmsg'", "#cmsg")
    )


def is_browser_challenge(
    status_code: int | None,
    headers: Mapping[object, object] | None,
    body: object,
) -> bool:
    if status_code not in {401, 403}:
        return False
    sample = str(body)[:CHALLENGE_BODY_SCAN_LENGTH].lower()
    if CHALLENGE_TEXT in sample:
        return True
    cmsg_marker = any(marker in sample for marker in ('id="cmsg"', "id='cmsg'", "#cmsg"))
    return cmsg_marker and has_lambda_generated_response(headers or {})


def body_markers(
    requested_url: object,
    response_url: object,
    status_code: int | None,
    headers: Mapping[object, object] | None,
    body: object,
) -> list[str]:
    del requested_url, response_url
    if is_browser_challenge(status_code, headers, body):
        return [BROWSER_CHALLENGE_MARKER]
    return []


def response_diagnostics(
    *,
    requested_url: object,
    status_code: int | None,
    decision: str,
    response_url: object,
    headers: Mapping[object, object] | None,
    body: object,
) -> dict[str, object]:
    return {
        "status": status_code,
        "decision": decision,
        "url": sanitize_url(response_url),
        "headers": sanitize_headers(headers),
        "body_markers": body_markers(requested_url, response_url, status_code, headers, body),
    }
