from typing import Optional
from pydantic import BaseModel
from enum import Enum
import datetime
import uuid


class UserSyncRequest(BaseModel):
    user_id: str


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime.datetime


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
