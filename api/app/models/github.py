from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Repo(BaseModel):
    id: int
    full_name: str
    private: bool
    html_url: str
    description: Optional[str] = None
    pushed_at: datetime
    stargazers_count: int


class GitHubStatusResponse(BaseModel):
    isConnected: bool
    username: Optional[str] = None
