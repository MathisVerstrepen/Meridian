import base64
import logging
from datetime import datetime

import httpx
import sentry_sdk
from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import HTTPException, status
from models.github import GithubCommitInfo, Repo as GithubRepo
from models.repository import RepositoryInfo
from services.crypto import decrypt_api_key

logger = logging.getLogger("uvicorn.error")


async def get_github_access_token(request, user_id: str) -> str:
    """
    Retrieves the GitHub access token for the specified user.
    """
    with sentry_sdk.start_span(op="github.auth", description="get_github_access_token"):
        token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")

        if not token_record:
            sentry_sdk.capture_message("GitHub token not found for user", level="warning")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub account is not connected.",
            )

        with sentry_sdk.start_span(op="crypto.decrypt", description="decrypt_api_key"):
            access_token = await decrypt_api_key(token_record.access_token)

        if not access_token:
            sentry_sdk.capture_message("Failed to decrypt GitHub token", level="error")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub access token is invalid.",
            )

        return access_token


async def get_latest_online_commit_info(
    repo_id: str, access_token: str, branch: str
) -> GithubCommitInfo:
    """Get the latest commit information for a specific branch of a GitHub repository"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Meridian Github Connector",
    }
    sentry_sdk.add_breadcrumb(
        category="github.api",
        message=f"Fetching latest online commit for {repo_id}",
        level="info",
        data={"branch": branch},
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo_id}/commits",
            params={"sha": branch, "per_page": 1},
            headers=headers,
        )

    if response.status_code != 200:
        raise Exception(f"GitHub API request failed: {response.text}")

    commit_data = response.json()
    if not commit_data:
        raise FileNotFoundError(f"No commits found for branch '{branch}' on remote.")

    commit_info = commit_data[0]

    return GithubCommitInfo(
        hash=commit_info["sha"],
        author=commit_info["commit"]["author"]["name"],
        date=datetime.fromisoformat(commit_info["commit"]["author"]["date"]),
    )


async def list_user_repos(gh_access_token: str) -> list:
    """
    Fetches and lists all available repositories from GitHub.
    This function always fetches fresh data from the GitHub API.
    """
    all_repos = []

    headers = {"Authorization": f"Bearer {gh_access_token}"}
    params = {"per_page": "100", "sort": "updated", "visibility": "all"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.github.com/user/repos", headers=headers, params=params
            )
            response.raise_for_status()
            for repo_data in response.json():
                repo = GithubRepo.model_validate(repo_data)
                provider_str = "github"
                encoded_provider_str = base64.urlsafe_b64encode(provider_str.encode()).decode()
                all_repos.append(
                    RepositoryInfo(
                        provider=provider_str,
                        encoded_provider=encoded_provider_str,
                        full_name=repo.full_name,
                        description=repo.description,
                        clone_url_ssh=f"git@github.com:{repo.full_name}.git",
                        clone_url_https=repo.html_url + ".git",
                        default_branch=repo.default_branch,
                        stargazers_count=repo.stargazers_count,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch GitHub repos: {e}")

    return all_repos
