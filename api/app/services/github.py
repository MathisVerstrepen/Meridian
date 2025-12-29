import asyncio
import base64
import logging
from datetime import datetime

import httpx
import sentry_sdk
from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import HTTPException, status
from models.github import GitHubIssue, PRCheckStatus, PRComment, PRCommit, PRExtendedContext
from models.github import Repo as GithubRepo
from models.repository import GitCommitInfo, RepositoryInfo
from services.crypto import decrypt_api_key

logger = logging.getLogger("uvicorn.error")


async def get_github_token_from_db(pg_engine, user_id: str) -> str:
    """
    Retrieves and decrypts the GitHub access token for the specified user using
    the provided DB engine.
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
                    f"Failed to fetch diff for PR #{pull_number} in {repo_full_name}: {response.status_code}"  # noqa: E501
                )
                return ""
        except Exception as e:
            logger.error(f"Error fetching PR diff: {e}")
            return ""


async def _fetch_gh_comments(
    client: httpx.AsyncClient, headers: dict, repo: str, number: int
) -> list[PRComment]:
    comments = []
    try:
        # Fetch both issue comments (general discussion) and review comments (code specific)
        issue_resp, review_resp = await asyncio.gather(
            client.get(
                f"https://api.github.com/repos/{repo}/issues/{number}/comments",
                headers=headers,
                params={"per_page": 50, "sort": "created", "direction": "desc"},
            ),
            client.get(
                f"https://api.github.com/repos/{repo}/pulls/{number}/comments",
                headers=headers,
                params={"per_page": 50, "sort": "created", "direction": "desc"},
            ),
            return_exceptions=True,
        )

        raw_items = []
        if isinstance(issue_resp, httpx.Response) and issue_resp.status_code == 200:
            raw_items.extend(issue_resp.json())
        if isinstance(review_resp, httpx.Response) and review_resp.status_code == 200:
            raw_items.extend(review_resp.json())

        # Sort combined list by date (oldest first)
        raw_items.sort(key=lambda x: x["created_at"])

        for item in raw_items:
            comments.append(
                PRComment(
                    id=item["id"],
                    user_login=item["user"]["login"],
                    body=item["body"] or "",
                    created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                    path=item.get("path"),
                    line=item.get("line") or item.get("original_line"),
                )
            )
    except Exception as e:
        logger.warning(f"Error fetching comments for {repo}#{number}: {e}")

    return comments


async def _fetch_gh_commits(
    client: httpx.AsyncClient, headers: dict, repo: str, number: int
) -> list[PRCommit]:
    commits = []
    try:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/pulls/{number}/commits",
            headers=headers,
            params={"per_page": 20},  # Limit to 20 commits
        )
        if resp.status_code == 200:
            for item in resp.json():
                commit_info = item["commit"]
                commits.append(
                    PRCommit(
                        sha=item["sha"],
                        message=commit_info["message"],
                        author_name=commit_info["author"]["name"],
                        date=datetime.fromisoformat(
                            commit_info["author"]["date"].replace("Z", "+00:00")
                        ),
                        verified=commit_info["verification"]["verified"],
                    )
                )
    except Exception as e:
        logger.warning(f"Error fetching commits for {repo}#{number}: {e}")
    return commits


async def _fetch_gh_checks(
    client: httpx.AsyncClient, headers: dict, repo: str, sha: str
) -> list[PRCheckStatus]:
    checks = []
    try:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("check_runs", []):
                checks.append(
                    PRCheckStatus(
                        name=item["name"],
                        status=item["status"],
                        conclusion=item["conclusion"],
                        details_url=item["html_url"],
                    )
                )
    except Exception as e:
        logger.warning(f"Error fetching checks for {repo}@{sha}: {e}")
    return checks


async def get_github_pr_extended_context(
    access_token: str, repo_full_name: str, pull_number: int
) -> PRExtendedContext:
    """
    Fetches additional context for a PR: comments, commits, and CI checks.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        comments, commits = await asyncio.gather(
            _fetch_gh_comments(client, headers, repo_full_name, pull_number),
            _fetch_gh_commits(client, headers, repo_full_name, pull_number),
        )

        checks = []
        if commits:
            latest_sha = commits[-1].sha
            checks = await _fetch_gh_checks(client, headers, repo_full_name, latest_sha)

    return PRExtendedContext(comments=comments, commits=commits, checks=checks)
