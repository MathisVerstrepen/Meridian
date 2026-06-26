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
    is_suspended: bool
    suspended_reason: str | None
    suspended_until: datetime | None
    created_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminMediaGenerationUsage(BaseModel):
    total: int
    recent_total: int
    pending: int
    processing: int
    retrying: int
    completed: int
    failed: int
    cancelled: int


class AdminUserUsageStats(BaseModel):
    total: int
    active: int
    active_days: int
    new_users: int
    verified: int
    unverified: int
    admins: int
    suspended: int
    free_plan: int
    premium_plan: int


class AdminGraphUsageStats(BaseModel):
    total: int
    active: int
    active_days: int
    created: int
    pinned: int
    temporary: int


class AdminQueryUsageStats(BaseModel):
    web_search_used: int
    link_extraction_used: int
    users_with_web_search_usage: int
    users_with_link_extraction_usage: int


class AdminStorageUsageStats(BaseModel):
    used_bytes: int
    users_with_storage: int


class AdminUsageDashboardResponse(BaseModel):
    total_users: int
    active_users: int
    active_days: int
    graph_count: int
    users: AdminUserUsageStats
    graphs: AdminGraphUsageStats
    query_usage: AdminQueryUsageStats
    storage: AdminStorageUsageStats
    image_generation: AdminMediaGenerationUsage
    video_generation: AdminMediaGenerationUsage
