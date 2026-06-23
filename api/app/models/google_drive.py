import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class GoogleDriveCallbackPayload(BaseModel):
    code: str


class GoogleDriveStatusResponse(BaseModel):
    isConnected: bool
    email: Optional[str] = None


class GoogleDriveFile(BaseModel):
    id: uuid.UUID
    external_id: str
    name: str
    path: str
    type: str
    source: str = "google_drive"
    provider: str = "google_drive"
    mime_type: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    modified_time: Optional[datetime] = None
    web_view_link: Optional[str] = None
    downloadable: bool = True
    cached: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GoogleDriveListResponse(BaseModel):
    files: list[GoogleDriveFile]
    next_page_token: Optional[str] = None
    incomplete_search: bool = False
