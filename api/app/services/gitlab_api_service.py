import logging

import httpx
from models.repository import RepositoryInfo

logger = logging.getLogger("uvicorn.error")


async def list_user_repos(pat: str) -> list[RepositoryInfo]:
    """
    Fetches a user's repositories from GitLab using a Personal Access Token.
    """
    headers = {"Authorization": f"Bearer {pat}"}
    repos_info = []
    api_url = "https://gitlab.com/api/v4/projects"
    params = {"owned": "true", "membership": "true", "per_page": 100}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, headers=headers, params=params)
            response.raise_for_status()
            repos_data = response.json()

            for repo in repos_data:
                repos_info.append(
                    RepositoryInfo(
                        provider="gitlab",
                        full_name=repo["path_with_namespace"],
                        description=repo.get("description"),
                        clone_url_ssh=repo["ssh_url_to_repo"],
                        clone_url_https=repo["http_url_to_repo"],
                        default_branch=repo["default_branch"] or "main",
                    )
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"GitLab API request failed: {e.response.text}")
            # Silently fail to not break the entire repo list if GitLab fails
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching GitLab repos: {e}")
            return []

    return repos_info
