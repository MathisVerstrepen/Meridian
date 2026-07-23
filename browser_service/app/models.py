from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FailureReason(str, Enum):
    HTTP_REJECTED = "http_rejected"
    CONNECTIVITY_EXHAUSTED = "connectivity_exhausted"
    CHALLENGE_UNRESOLVED = "challenge_unresolved"
    BROWSER_FAILED = "browser_failed"
    UNUSABLE_CONTENT = "unusable_content"
    FETCH_FAILED = "fetch_failed"


class FetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    url: str = Field(min_length=1)


class FetchErrorBody(BaseModel):
    reason: FailureReason
    status_code: int | None = Field(default=None, ge=400, le=599)


class FetchSuccess(BaseModel):
    request_id: UUID
    html: str


class FetchFailure(BaseModel):
    request_id: UUID
    error: FetchErrorBody


class HealthReady(BaseModel):
    status: Literal["ok"] = "ok"
    browser_build: str
    capacity: Literal[4] = 4
    queue_capacity: Literal[8] = 8


class BrowserFetchError(Exception):
    def __init__(self, reason: FailureReason, status_code: int | None = None) -> None:
        self.reason = reason
        self.status_code = (
            status_code
            if isinstance(status_code, int)
            and not isinstance(status_code, bool)
            and 400 <= status_code <= 599
            else None
        )
        super().__init__(reason.value)
