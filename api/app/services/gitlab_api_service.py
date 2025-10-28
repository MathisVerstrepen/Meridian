import logging
from datetime import datetime
from urllib.parse import quote, urljoin

import httpx
import pybase64 as base64
from models.repository import GitCommitInfo, RepositoryInfo

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


async def get_latest_online_commit_info_gl(
    instance_url: str,
    project_path: str,
    pat: str,
    branch: str,
    http_client: httpx.AsyncClient,
) -> GitCommitInfo:
    """
    Get the latest commit information for a specific branch of a GitLab project.
    """
    headers = {
        "Accept": "application/json",
        "Private-Token": pat,
    }

    params = {
        "ref_name": str(branch),
        "per_page": str(1),
    }

    url = f"{instance_url.strip('/')}/api/v4/projects/{quote(project_path, safe='')}/repository/commits"  # noqa:E501

    response = await http_client.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"GitLab API request failed: {response.text}")

    commits = response.json()
    if not commits:
        raise FileNotFoundError(f"No commits found for branch '{branch}' on remote.")

    commit = commits[0]

    return GitCommitInfo(
        hash=commit["id"],
        author=commit["author_name"],
        date=datetime.fromisoformat(commit["created_at"].replace("Z", "+00:00")),
    )
