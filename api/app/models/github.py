from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Repo(BaseModel):
    id: int
    full_name: str
    private: bool
    html_url: str
    description: Optional[str] = None
    pushed_at: datetime
    stargazers_count: int
    default_branch: str


class GitHubStatusResponse(BaseModel):
    isConnected: bool
    username: Optional[str] = None


class FileTreeNode(BaseModel):
    name: str
    type: str  # "file" or "directory"
    path: str
    children: list["FileTreeNode"] = []


class GitHubIssue(BaseModel):
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str
    html_url: str
    is_pull_request: bool
    user_login: str
    user_avatar: Optional[str] = None
    created_at: datetime
    updated_at: datetime
