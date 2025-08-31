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
    children: Optional[list["FileTreeNode"]] = None
