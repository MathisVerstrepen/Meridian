import logging
from urllib.parse import urljoin
import pybase64 as base64

import httpx
from models.repository import RepositoryInfo

logger = logging.getLogger("uvicorn.error")


async def list_user_repos(pat: str, instance_url: str) -> list[RepositoryInfo]:
    """
    Fetches a user's repositories from GitLab using a Personal Access Token.
    """
    repos_info = []
    base_api_url = f"{instance_url.strip('/')}/api/v4/"
    projects_url = urljoin(base_api_url, "projects")
    api_url = f"{projects_url}?private_token={pat}&membership=true&per_page=100"
    headers = {
        "Accept": "application/json",
        "Cache-Control": "no-cache",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            repos_data = response.json()

            for repo in repos_data:
                provider_str = f"gitlab:{instance_url.strip('/')}"
                encoded_provider_str = base64.urlsafe_b64encode(provider_str.encode()).decode()
                repos_info.append(
                    RepositoryInfo(
                        provider=provider_str,
                        encoded_provider=encoded_provider_str,
                        full_name=repo["path_with_namespace"],
                        description=repo.get("description"),
                        clone_url_ssh=repo["ssh_url_to_repo"],
                        clone_url_https=repo["http_url_to_repo"],
                        default_branch=repo["default_branch"] or "main",
                        stargazers_count=repo["star_count"],
                    )
                )
        except httpx.HTTPStatusError as e:
            logger.error(f"GitLab API request failed for {instance_url}: {e.response.text}")
            # Silently fail to not break the entire repo list if one instance fails
            return []
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching GitLab repos from {instance_url}: {e}"
            )
            return []

    return repos_info
