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


class GitHubStatusResponse(BaseModel):
    isConnected: bool
    username: Optional[str] = None


class FileTreeNode(BaseModel):
    name: str
    type: str  # "file" or "directory"
    path: str
    children: list["FileTreeNode"] = []


class GithubCommitInfo(BaseModel):
    hash: str
    author: str
    date: datetime


class GithubCommitState(BaseModel):
    latest_local: GithubCommitInfo
    latest_online: GithubCommitInfo
    is_up_to_date: bool
