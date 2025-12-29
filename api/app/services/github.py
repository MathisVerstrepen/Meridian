import base64
import logging
from datetime import datetime

import httpx
import sentry_sdk
from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import HTTPException, status
from models.github import GitHubIssue
from models.github import Repo as GithubRepo
from models.repository import GitCommitInfo, RepositoryInfo
from services.crypto import decrypt_api_key

logger = logging.getLogger("uvicorn.error")


async def get_github_token_from_db(pg_engine, user_id: str) -> str:
    """
    Retrieves and decrypts the GitHub access token for the specified user using the provided DB engine.
    """
    token_record = await get_provider_token(pg_engine, user_id, "github")

    if not token_record:
        raise Exception("GitHub account is not connected.")

    access_token = await decrypt_api_key(token_record.access_token)

    if not access_token:
        raise Exception("GitHub access token is invalid.")

    return access_token


async def get_github_access_token(request, user_id: str) -> str:
    """
    Retrieves the GitHub access token for the specified user.
    """
    with sentry_sdk.start_span(op="github.auth", description="get_github_access_token"):
        try:
            return await get_github_token_from_db(request.app.state.pg_engine, user_id)
        except Exception as e:
            sentry_sdk.capture_message(f"GitHub token error: {e}", level="warning")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )


async def get_latest_online_commit_info_gh(
    repo_id: str, access_token: str, branch: str
) -> GitCommitInfo:
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

    return GitCommitInfo(
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


async def list_repo_issues(
    access_token: str, repo_full_name: str, state: str = "open"
) -> list[GitHubIssue]:
    """
    Fetches issues and pull requests from a specific GitHub repository.
    """
    issues = []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {
        "state": state,
        "per_page": "100",
        "sort": "updated",
        "direction": "desc",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/issues",
                headers=headers,
                params=params,
            )
            response.raise_for_status()

            for item in response.json():
                issues.append(
                    GitHubIssue(
                        id=item["id"],
                        number=item["number"],
                        title=item["title"],
                        body=item.get("body"),
                        state=item["state"],
                        html_url=item["html_url"],
                        is_pull_request="pull_request" in item,
                        user_login=item["user"]["login"],
                        user_avatar=item["user"].get("avatar_url"),
                        created_at=datetime.fromisoformat(
                            item["created_at"].replace("Z", "+00:00")
                        ),
                        updated_at=datetime.fromisoformat(
                            item["updated_at"].replace("Z", "+00:00")
                        ),
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch GitHub issues for {repo_full_name}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch issues: {str(e)}",
            )

    return issues


async def get_pr_diff(access_token: str, repo_full_name: str, pull_number: int) -> str:
    """
    Fetches the diff for a specific Pull Request.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "Meridian Github Connector",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pull_number}",
                headers=headers,
            )
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(
                    f"Failed to fetch diff for PR #{pull_number} in {repo_full_name}: {response.status_code}"
                )
                return ""
        except Exception as e:
            logger.error(f"Error fetching PR diff: {e}")
            return ""
