from typing import Optional

from pydantic import BaseModel


class RepositoryInfo(BaseModel):
    provider: str
    encoded_provider: str
    full_name: str
    description: Optional[str] = None
    clone_url_ssh: str
    clone_url_https: str
    default_branch: str
    stargazers_count: Optional[int] = None
