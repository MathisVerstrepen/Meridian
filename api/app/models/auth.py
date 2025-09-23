import datetime
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class UserSyncRequest(BaseModel):
    user_id: str


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    oauth_provider: Optional[str] = None
    created_at: datetime.datetime
    plan_type: str
    is_admin: bool


class OAuthSyncResponse(BaseModel):
    accessToken: str
    refreshToken: str
    user: UserRead


class ProviderEnum(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"
    USERPASS = "userpass"


class UserPass(BaseModel):
    username: str
    password: str
