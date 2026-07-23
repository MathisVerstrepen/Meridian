from enum import Enum


class LinkExtractionFailureReason(str, Enum):
    HTTP_REJECTED = "http_rejected"
    CONNECTIVITY_EXHAUSTED = "connectivity_exhausted"
    CHALLENGE_UNRESOLVED = "challenge_unresolved"
    BROWSER_FAILED = "browser_failed"
    UNUSABLE_CONTENT = "unusable_content"
    FETCH_FAILED = "fetch_failed"


class LinkExtractionError(Exception):
    def __init__(
        self,
        reason: LinkExtractionFailureReason,
        status_code: int | None = None,
    ) -> None:
        self.reason = (
            reason
            if isinstance(reason, LinkExtractionFailureReason)
            else LinkExtractionFailureReason.FETCH_FAILED
        )
        super().__init__(self.reason.value)
        self.status_code = (
            status_code
            if isinstance(status_code, int)
            and not isinstance(status_code, bool)
            and 400 <= status_code <= 599
            else None
        )


class BrowserFetchError(LinkExtractionError):
    pass


def failure_user_message(error: LinkExtractionError) -> str:
    if error.reason is LinkExtractionFailureReason.HTTP_REJECTED:
        if error.status_code is not None:
            return f"The page rejected the request (HTTP {error.status_code})."
        return "The page rejected the request."
    if error.reason is LinkExtractionFailureReason.CONNECTIVITY_EXHAUSTED:
        return "The page could not be reached after temporary connection failures."
    if error.reason is LinkExtractionFailureReason.CHALLENGE_UNRESOLVED:
        return "The page presented a browser challenge that could not be resolved."
    if error.reason is LinkExtractionFailureReason.BROWSER_FAILED:
        return "The browser fallback could not initialize or load the page."
    if error.reason is LinkExtractionFailureReason.UNUSABLE_CONTENT:
        return "The page was fetched, but no usable content could be extracted."
    return "The page could not be fetched or processed."
