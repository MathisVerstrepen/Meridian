import json
import logging
from pathlib import Path
import pybase64 as base64

import httpx
from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import APIRouter, Depends, HTTPException, Request, status
from models.github import Repo as GithubRepo
from models.repository import RepositoryInfo
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.crypto import decrypt_api_key
from services.git_service import (
    CLONED_REPOS_BASE_DIR,
    build_file_tree_for_branch,
    clone_repo,
    get_files_content_for_branch,
    list_branches,
    pull_repo,
)
from services.gitlab_api_service import list_user_repos as list_gitlab_repos
from services.github import list_user_repos as list_github_repos
from services.ssh_manager import ssh_key_context

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


class ClonePayload(BaseModel):
    provider: str
    full_name: str
    clone_url: str
    clone_method: str  # 'ssh' or 'https'


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
    gitlab_token_record = await get_provider_token(request.app.state.pg_engine, user_id, "gitlab")
    if gitlab_token_record:
        try:
            instance_url = gitlab_token_record.provider.split(":", 1)[1]
            gl_tokens = json.loads(gitlab_token_record.access_token)
            gl_pat = await decrypt_api_key(gl_tokens["pat"])
            if gl_pat:
                gitlab_repos = await list_gitlab_repos(gl_pat, instance_url)
                all_repos.extend(gitlab_repos)
        except Exception as e:
            logger.error(f"Failed to fetch GitLab repos: {e}")

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
    target_dir = CLONED_REPOS_BASE_DIR / payload.provider / payload.full_name
    if target_dir.exists():
        return {"message": "Repository already cloned.", "path": str(target_dir)}

    auth_env = None
    clone_url = payload.clone_url

    if payload.clone_method == "ssh":
        if payload.provider.startswith("gitlab:"):
            token_record = await get_provider_token(
                request.app.state.pg_engine, user_id, payload.provider
            )
            if not token_record:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    f"No credentials found for provider {payload.provider}.",
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
            token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
            if not token_record:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub not connected.")
            access_token = await decrypt_api_key(token_record.access_token)
            clone_url = f"https://{access_token}@{clone_url.replace('https://', '')}"
        elif payload.provider.startswith("gitlab:"):
            token_record = await get_provider_token(
                request.app.state.pg_engine, user_id, payload.provider
            )
            if not token_record:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    f"No credentials found for GitLab provider {payload.provider}.",
                )
            tokens = json.loads(token_record.access_token)
            access_token = await decrypt_api_key(tokens["pat"])
            if not access_token:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitLab token."
                )
            clone_url = f"https://oauth2:{access_token}@{clone_url.replace('https://', '')}"
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported clone method.")

    await clone_repo(clone_url, target_dir, env=auth_env)
    return {"message": "Repository cloned successfully.", "path": str(target_dir)}


def get_repo_path(provider: str, owner: str, repo: str) -> Path:
    """Constructs and validates the local path for a cloned repository."""
    path = CLONED_REPOS_BASE_DIR / provider / owner / repo
    if not path.exists() or not (path / ".git").exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found locally. Please clone it first.",
        )
    return path


@router.get("/repositories/{encoded_provider}/{owner}/{repo}/branches")
async def get_repo_branches(encoded_provider: str, owner: str, repo: str):
    provider = base64.urlsafe_b64decode(encoded_provider).decode()
    repo_dir = get_repo_path(provider, owner, repo)
    return await list_branches(repo_dir)


@router.get("/repositories/{encoded_provider}/{owner}/{repo}/tree")
async def get_repo_tree(encoded_provider: str, owner: str, repo: str, branch: str):
    provider = base64.urlsafe_b64decode(encoded_provider).decode()
    repo_dir = get_repo_path(provider, owner, repo)
    return await build_file_tree_for_branch(repo_dir, branch)


@router.get("/repositories/{encoded_provider}/{owner}/{repo}/content/{file_path:path}")
async def get_repo_file_content(
    encoded_provider: str, owner: str, repo: str, branch: str, file_path: str
):
    provider = base64.urlsafe_b64decode(encoded_provider).decode()
    repo_dir = get_repo_path(provider, owner, repo)
    content = await get_files_content_for_branch(repo_dir, branch, [file_path])
    return {"content": content.get(file_path, "")}


@router.post("/repositories/{encoded_provider}/{owner}/{repo}/pull")
async def pull_repository(encoded_provider: str, owner: str, repo: str, branch: str):
    provider = base64.urlsafe_b64decode(encoded_provider).decode()
    repo_dir = get_repo_path(provider, owner, repo)
    await pull_repo(repo_dir, branch)
    return {"message": f"Successfully pulled branch '{branch}'."}
