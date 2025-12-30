from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminUserListItem(BaseModel):
    id: UUID
    username: str
    email: str | None
    avatar_url: str | None
    oauth_provider: str | None
    plan_type: str
    is_verified: bool
    is_admin: bool
    created_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserListItem]
    total: int
    page: int
    page_size: int
