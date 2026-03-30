import json
import logging
from pathlib import Path

import pybase64 as base64
from database.pg.token_ops.provider_token_crud import (
    get_provider_token,
    get_provider_tokens_by_prefix,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.github import GitHubIssue
from models.repository import GitCommitState, RepositoryInfo
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.crypto import decrypt_api_key
from services.git_service import (
    CLONED_REPOS_BASE_DIR,
    build_file_tree_for_branch,
    build_github_auth_env,
    build_gitlab_auth_env,
    clone_repo,
    get_files_content_for_branch,
    get_latest_local_commit_info,
    list_branches,
    pull_repo,
)
from services.github import get_latest_online_commit_info_gh
from services.github import list_repo_issues as list_github_issues
from services.github import list_user_repos as list_github_repos
from services.gitlab_api_service import get_latest_online_commit_info_gl
from services.gitlab_api_service import list_repo_issues as list_gitlab_issues
from services.gitlab_api_service import list_user_repos as list_gitlab_repos
from services.gitlab_provider import (
    GITLAB_PROVIDER_PREFIX,
    build_gitlab_provider_key,
    get_gitlab_instance_url,
    get_gitlab_storage_provider,
)
from services.ssh_manager import ssh_key_context

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


class ClonePayload(BaseModel):
    provider: str
    full_name: str
    clone_url: str
    clone_method: str  # 'ssh' or 'https'


async def get_git_operation_env(request: Request, user_id: str, provider: str) -> dict | None:
    if provider == "github":
        token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
        if not token_record:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub not connected.")

        access_token = await decrypt_api_key(token_record.access_token)
        if not access_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitHub token."
            )

        return build_github_auth_env(access_token)

    if provider.startswith("gitlab:"):
        instance_url = get_gitlab_instance_url(provider)
        token_record = await get_provider_token(
            request.app.state.pg_engine,
            user_id,
            build_gitlab_provider_key(instance_url),
        )
        if not token_record:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                f"No credentials found for GitLab provider {provider}.",
            )

        tokens = json.loads(token_record.access_token)
        access_token = await decrypt_api_key(tokens["pat"])
        if not access_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitLab token."
            )

        return build_gitlab_auth_env(instance_url, access_token)

    return None


@router.get("/repositories", response_model=list[RepositoryInfo])
async def list_available_repositories(
    request: Request, user_id: str = Depends(get_current_user_id)
):
    """
    Fetches and lists all available repositories from connected providers (GitHub, GitLab).
    This endpoint always fetches fresh data from the respective APIs.
    """
    all_repos = []

    # Fetch from GitHub
    github_token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
    if github_token_record:
        try:
            gh_access_token = await decrypt_api_key(github_token_record.access_token)
            if gh_access_token:
                github_repos = await list_github_repos(gh_access_token)
                all_repos.extend(github_repos)
        except Exception as e:
            logger.error(f"Failed to fetch GitHub repos: {e}")

    # Fetch from GitLab
    gitlab_token_records = await get_provider_tokens_by_prefix(
        request.app.state.pg_engine, user_id, GITLAB_PROVIDER_PREFIX
    )
    for gitlab_token_record in gitlab_token_records:
        try:
            instance_url = get_gitlab_instance_url(gitlab_token_record.provider)
            gl_tokens = json.loads(gitlab_token_record.access_token)
            gl_pat = await decrypt_api_key(gl_tokens["pat"])
            if gl_pat:
                gitlab_repos = await list_gitlab_repos(gl_pat, instance_url)
                all_repos.extend(gitlab_repos)
        except Exception as e:
            logger.error(f"Failed to fetch GitLab repos for {gitlab_token_record.provider}: {e}")

    return all_repos


@router.post("/repositories/clone", status_code=status.HTTP_201_CREATED)
async def clone_repository_endpoint(
    request: Request, payload: ClonePayload, user_id: str = Depends(get_current_user_id)
):
    """
    Clones a repository to the local filesystem for interaction.
    This operation is tracked in the database, but this implementation detail is omitted
    as per the prompt's focus on API-driven listing and interaction.
    """
    raw_provider = payload.provider
    storage_provider = raw_provider
    if raw_provider.startswith("gitlab:"):
        storage_provider = get_gitlab_storage_provider(raw_provider)
    target_dir = CLONED_REPOS_BASE_DIR / storage_provider / payload.full_name
    if target_dir.exists():
        return {"message": "Repository already cloned.", "path": str(target_dir)}

    auth_env = None
    clone_url = payload.clone_url

    if payload.clone_method == "ssh":
        if payload.provider.startswith("gitlab:"):
            token_record = await get_provider_token(
                request.app.state.pg_engine,
                user_id,
                build_gitlab_provider_key(get_gitlab_instance_url(raw_provider)),
            )
            if not token_record:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    f"No credentials found for provider {raw_provider}.",
                )

            tokens = json.loads(token_record.access_token)
            ssh_key = await decrypt_api_key(tokens["ssh_key"])
            if not ssh_key:
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt key.")
            async with ssh_key_context(ssh_key) as env:
                await clone_repo(clone_url, target_dir, env=env)
            return {
                "message": "Repository cloned successfully via SSH.",
                "path": str(target_dir),
            }
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "SSH cloning not configured for this provider."
            )

    elif payload.clone_method == "https":
        if payload.provider == "github":
            auth_env = await get_git_operation_env(request, user_id, "github")
        elif payload.provider.startswith("gitlab:"):
            auth_env = await get_git_operation_env(request, user_id, raw_provider)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported clone method.")

    await clone_repo(clone_url, target_dir, env=auth_env)
    return {"message": "Repository cloned successfully.", "path": str(target_dir)}


def get_repo_path(provider: str, project_path: str) -> Path:
    """Constructs and validates the local path for a cloned repository."""
    cloned_repos_root = CLONED_REPOS_BASE_DIR.resolve()
    storage_provider = provider
    if provider.startswith("gitlab:"):
        storage_provider = get_gitlab_storage_provider(provider)
    provider_root = (cloned_repos_root / storage_provider).resolve(strict=False)

    try:
        provider_root.relative_to(cloned_repos_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository provider path.",
        ) from exc

    path = (provider_root / project_path).resolve(strict=False)
    try:
        path.relative_to(provider_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository path.",
        ) from exc

    if not path.exists() or not (path / ".git").exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found locally at {path}. Please clone it first.",
        )
    return path


def decode_provider(encoded_provider: str) -> str:
    try:
        return base64.urlsafe_b64decode(encoded_provider).decode()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider encoding.",
        ) from exc


@router.get("/repositories/{encoded_provider}/{project_path:path}/branches")
async def get_repo_branches(
    encoded_provider: str,
    project_path: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    provider = decode_provider(encoded_provider)
    repo_dir = get_repo_path(provider, project_path)
    auth_env = await get_git_operation_env(request, user_id, provider)
    return await list_branches(repo_dir, env=auth_env)


@router.get("/repositories/{encoded_provider}/{project_path:path}/tree")
async def get_repo_tree(
    encoded_provider: str,
    project_path: str,
    branch: str,
    user_id: str = Depends(get_current_user_id),
):
    provider = decode_provider(encoded_provider)
    repo_dir = get_repo_path(provider, project_path)
    return await build_file_tree_for_branch(repo_dir, branch)


@router.get("/repositories/{encoded_provider}/{project_path:path}/content/{file_path:path}")
async def get_repo_file_content(
    encoded_provider: str,
    project_path: str,
    branch: str,
    file_path: str,
    user_id: str = Depends(get_current_user_id),
):
    provider = decode_provider(encoded_provider)
    repo_dir = get_repo_path(provider, project_path)
    content = await get_files_content_for_branch(repo_dir, branch, [file_path])
    return {"content": content.get(file_path, "")}


@router.post("/repositories/{encoded_provider}/{project_path:path}/pull")
async def pull_repository(
    encoded_provider: str,
    project_path: str,
    branch: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    provider = decode_provider(encoded_provider)
    repo_dir = get_repo_path(provider, project_path)
    auth_env = await get_git_operation_env(request, user_id, provider)
    await pull_repo(repo_dir, branch, env=auth_env)
    return {"message": f"Successfully pulled branch '{branch}'."}


@router.get(
    "/repositories/{encoded_provider}/{project_path:path}/issues", response_model=list[GitHubIssue]
)
async def get_repo_issues(
    encoded_provider: str,
    project_path: str,
    request: Request,
    state: str = "open",
    user_id: str = Depends(get_current_user_id),
):
    """
    Fetches issues and PRs/MRs for a specific repository (GitHub or GitLab).
    """
    provider = decode_provider(encoded_provider)

    if provider.startswith("gitlab:"):
        instance_url = get_gitlab_instance_url(provider)
        token_record = await get_provider_token(
            request.app.state.pg_engine,
            user_id,
            build_gitlab_provider_key(instance_url),
        )
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"GitLab not connected for {instance_url}.",
            )

        tokens = json.loads(token_record.access_token)
        gl_pat = await decrypt_api_key(tokens["pat"])
        if not gl_pat:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitLab token."
            )

        return await list_gitlab_issues(gl_pat, instance_url, project_path, state)

    elif provider == "github":
        token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
        if not token_record:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub not connected.")
        gh_token = await decrypt_api_key(token_record.access_token)
        if not gh_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitHub token."
            )

        return await list_github_issues(gh_token, project_path, state)

    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Provider '{provider}' is not supported for issue fetching.",
        )


@router.get("/repositories/{encoded_provider}/{project_path:path}/commit-state")
async def get_repository_commit_state(
    encoded_provider: str,
    project_path: str,
    branch: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> GitCommitState:
    """
    Generic provider-agnostic commit state endpoint.
    Compares local vs online latest commit and returns whether the local clone is up-to-date.
    Works with GitHub and GitLab (and any future provider with the same shape).
    """
    provider = decode_provider(encoded_provider)
    repo_dir = get_repo_path(provider, project_path)

    if provider.startswith("gitlab:"):
        instance_url = get_gitlab_instance_url(provider)
        token_record = await get_provider_token(
            request.app.state.pg_engine,
            user_id,
            build_gitlab_provider_key(instance_url),
        )
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"GitLab not connected for {instance_url}.",
            )

        tokens = json.loads(token_record.access_token)
        gl_pat = await decrypt_api_key(tokens["pat"])
        if not gl_pat:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitLab token."
            )

        # project_path now contains the full path with namespace (e.g., group/subgroup/repo)
        latest_online = await get_latest_online_commit_info_gl(
            instance_url=instance_url,
            project_path=project_path,
            pat=gl_pat,
            branch=branch,
            http_client=request.app.state.http_client,
        )
    elif provider == "github":
        token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
        if not token_record:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub not connected.")
        gh_token = await decrypt_api_key(token_record.access_token)
        if not gh_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitHub token."
            )

        latest_online = await get_latest_online_commit_info_gh(
            repo_id=project_path,
            access_token=gh_token,
            branch=branch,
        )
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Provider '{provider}' is not supported by this endpoint.",
        )

    latest_local = await get_latest_local_commit_info(repo_dir, branch)

    is_up_to_date = latest_local.hash == latest_online.hash

    return GitCommitState(
        latest_local=latest_local,
        latest_online=latest_online,
        is_up_to_date=is_up_to_date,
    )
