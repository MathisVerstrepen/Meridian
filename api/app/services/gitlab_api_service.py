import asyncio
import logging
from datetime import datetime
from urllib.parse import quote, urljoin

import httpx
import pybase64 as base64
from models.github import GitHubIssue, PRCheckStatus, PRComment, PRCommit, PRExtendedContext
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


async def list_repo_issues(
    pat: str, instance_url: str, project_path: str, state: str = "open"
) -> list[GitHubIssue]:
    """
    Fetches issues and merge requests from a specific GitLab project.
    Maps them to the GitHubIssue model for consistency.
    """
    issues = []

    # Map 'open'/'closed'/'all' to GitLab's state param
    gl_state = "opened" if state == "open" else state
    if state == "all":
        gl_state = "all"

    # Prepare base URL
    base_api_url = (
        f"https://{instance_url.strip('/')}/api/v4/projects/{quote(project_path, safe='')}"
    )
    headers = {"Private-Token": pat}

    async with httpx.AsyncClient() as client:
        # 1. Fetch Issues
        issues_url = f"{base_api_url}/issues"
        issues_params = {"per_page": "100", "scope": "all"}
        if state != "all":
            issues_params["state"] = gl_state

        try:
            resp = await client.get(issues_url, headers=headers, params=issues_params)
            resp.raise_for_status()
            for item in resp.json():
                issues.append(
                    GitHubIssue(
                        id=item["id"],
                        number=item["iid"],
                        title=item["title"],
                        body=item.get("description"),
                        state="open" if item["state"] == "opened" else "closed",
                        html_url=item["web_url"],
                        is_pull_request=False,
                        user_login=item["author"]["username"],
                        user_avatar=item["author"].get("avatar_url"),
                        created_at=datetime.fromisoformat(
                            item["created_at"].replace("Z", "+00:00")
                        ),
                        updated_at=datetime.fromisoformat(
                            item["updated_at"].replace("Z", "+00:00")
                        ),
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch GitLab issues for {project_path}: {e}")

        # 2. Fetch Merge Requests
        mr_url = f"{base_api_url}/merge_requests"
        mr_params = {"per_page": "100", "scope": "all"}
        if state != "all":
            mr_params["state"] = gl_state

        try:
            resp = await client.get(mr_url, headers=headers, params=mr_params)
            resp.raise_for_status()
            for item in resp.json():
                # Map MR state to open/closed
                mr_state = item["state"]
                mapped_state = "open" if mr_state in ["opened", "locked"] else "closed"

                issues.append(
                    GitHubIssue(
                        id=item["id"],
                        number=item["iid"],
                        title=item["title"],
                        body=item.get("description"),
                        state=mapped_state,
                        html_url=item["web_url"],
                        is_pull_request=True,
                        user_login=item["author"]["username"],
                        user_avatar=item["author"].get("avatar_url"),
                        created_at=datetime.fromisoformat(
                            item["created_at"].replace("Z", "+00:00")
                        ),
                        updated_at=datetime.fromisoformat(
                            item["updated_at"].replace("Z", "+00:00")
                        ),
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch GitLab MRs for {project_path}: {e}")

    # Sort by updated_at desc
    issues.sort(key=lambda x: x.updated_at, reverse=True)
    return issues


async def get_mr_diff(pat: str, instance_url: str, project_path: str, mr_iid: int) -> str:
    """
    Fetches the diff for a specific Merge Request using the .diff endpoint.
    """
    headers = {"Private-Token": pat}
    url = f"https://{instance_url.strip('/')}/api/v4/projects/{quote(project_path, safe='')}/merge_requests/{mr_iid}/raw_diffs"  # noqa:E501

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(
                    f"Failed to fetch diff for MR #{mr_iid} in {project_path}: {response.status_code}"  # noqa: E501
                )
                return ""
        except Exception as e:
            logger.error(f"Error fetching MR diff: {e}")
            return ""


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

    url = f"https://{instance_url.strip('/')}/api/v4/projects/{quote(project_path, safe='')}/repository/commits"  # noqa:E501

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


async def _fetch_gl_notes(
    client: httpx.AsyncClient, headers: dict, base_url: str, mr_iid: int
) -> list[PRComment]:
    comments = []
    try:
        # Fetch MR notes (comments)
        url = f"{base_url}/merge_requests/{mr_iid}/notes"
        resp = await client.get(
            url, headers=headers, params={"per_page": 50, "sort": "asc", "order_by": "created_at"}
        )
        if resp.status_code == 200:
            for item in resp.json():
                if item.get("system", False):
                    continue

                comments.append(
                    PRComment(
                        id=item["id"],
                        user_login=item["author"]["username"],
                        body=item["body"],
                        created_at=datetime.fromisoformat(
                            item["created_at"].replace("Z", "+00:00")
                        ),
                        path=None,
                        line=None,
                    )
                )
    except Exception as e:
        logger.warning(f"Error fetching GitLab notes for MR #{mr_iid}: {e}")
    return comments


async def _fetch_gl_commits(
    client: httpx.AsyncClient, headers: dict, base_url: str, mr_iid: int
) -> list[PRCommit]:
    commits = []
    try:
        url = f"{base_url}/merge_requests/{mr_iid}/commits"
        resp = await client.get(url, headers=headers, params={"per_page": 20})
        if resp.status_code == 200:
            for item in resp.json():
                commits.append(
                    PRCommit(
                        sha=item["id"],
                        message=item["message"],
                        author_name=item["author_name"],
                        date=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                        verified=False,
                    )
                )
    except Exception as e:
        logger.warning(f"Error fetching GitLab commits for MR #{mr_iid}: {e}")
    return commits


async def _fetch_gl_pipelines(
    client: httpx.AsyncClient, headers: dict, base_url: str, mr_iid: int
) -> list[PRCheckStatus]:
    checks = []
    try:
        # Get latest pipeline
        url = f"{base_url}/merge_requests/{mr_iid}/pipelines"
        resp = await client.get(url, headers=headers, params={"per_page": 1})
        if resp.status_code == 200 and resp.json():
            pipeline = resp.json()[0]
            # Add overall status
            checks.append(
                PRCheckStatus(
                    name=f"Pipeline #{pipeline['id']}",
                    status=pipeline["status"],
                    conclusion=pipeline["status"],
                    details_url=pipeline["web_url"],
                )
            )
            # Fetch jobs for details
            jobs_url = f"{base_url.replace('/merge_requests', '')}/pipelines/{pipeline['id']}/jobs"
            jobs_resp = await client.get(jobs_url, headers=headers, params={"per_page": 20})
            if jobs_resp.status_code == 200:
                for job in jobs_resp.json():
                    if job["status"] in ["failed", "canceled"]:
                        checks.append(
                            PRCheckStatus(
                                name=job["name"],
                                status=job["status"],
                                conclusion=job["status"],
                                details_url=job["web_url"],
                            )
                        )
    except Exception as e:
        logger.warning(f"Error fetching GitLab pipelines for MR #{mr_iid}: {e}")
    return checks


async def get_gitlab_mr_extended_context(
    pat: str, instance_url: str, project_path: str, mr_iid: int
) -> PRExtendedContext:
    """
    Fetches additional context for a GitLab MR: notes, commits, and pipelines.
    """
    base_api_url = (
        f"https://{instance_url.strip('/')}/api/v4/projects/{quote(project_path, safe='')}"
    )
    headers = {"Private-Token": pat}

    async with httpx.AsyncClient() as client:
        comments, commits, checks = await asyncio.gather(
            _fetch_gl_notes(client, headers, base_api_url, mr_iid),
            _fetch_gl_commits(client, headers, base_api_url, mr_iid),
            _fetch_gl_pipelines(client, headers, base_api_url, mr_iid),
        )

    return PRExtendedContext(comments=comments, commits=commits, checks=checks)
