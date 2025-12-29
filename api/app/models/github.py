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


class PRComment(BaseModel):
    id: str | int
    user_login: str
    body: str
    created_at: datetime
    path: Optional[str] = None
    line: Optional[int] = None


class PRCommit(BaseModel):
    sha: str
    message: str
    author_name: str
    date: datetime
    verified: bool = False


class PRCheckStatus(BaseModel):
    name: str
    status: str
    conclusion: Optional[str] = None
    details_url: Optional[str] = None


class PRExtendedContext(BaseModel):
    comments: list[PRComment] = []
    commits: list[PRCommit] = []
    checks: list[PRCheckStatus] = []
