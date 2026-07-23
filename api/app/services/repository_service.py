import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from database.pg.models import Repository
from database.pg.repository_ops.repository_crud import (
    get_owned_repository,
    update_owned_repository_status,
)
from database.pg.token_ops.provider_token_crud import (
    get_provider_token,
    get_provider_tokens_by_prefix,
)
from fastapi import HTTPException, Request, status
from services.crypto import decrypt_api_key
from services.git_service import (
    build_file_tree_for_branch,
    build_github_auth_env,
    build_gitlab_auth_env,
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
)
from services.repository_paths import build_repo_path, clone_repository_lock
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")
REPOSITORY_NOT_FOUND = "Repository not found."


def canonicalize_repository_identity(provider: str, project_path: str) -> tuple[str, str]:
    normalized_project = project_path.strip()
    if (
        not normalized_project
        or normalized_project.startswith("/")
        or "\\" in normalized_project
        or any(part in {"", ".", ".."} for part in normalized_project.split("/"))
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid repository path.")

    if provider == "github":
        normalized_provider = provider
    elif provider.startswith(GITLAB_PROVIDER_PREFIX):
        try:
            normalized_provider = build_gitlab_provider_key(get_gitlab_instance_url(provider))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Invalid repository provider."
            ) from exc
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported repository provider.")

    return normalized_provider, normalized_project


async def _get_owned_repository(
    request: Request, user_id: str, provider: str, project_path: str
) -> Repository:
    provider, project_path = canonicalize_repository_identity(provider, project_path)
    repository = await get_owned_repository(
        request.app.state.pg_engine, user_id, provider, project_path
    )
    if repository is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, REPOSITORY_NOT_FOUND)
    return repository


async def _get_owned_ready_repository(
    request: Request, user_id: str, provider: str, project_path: str
) -> tuple[Repository, Path]:
    repository = await _get_owned_repository(request, user_id, provider, project_path)
    if repository.status != "pulled":
        raise HTTPException(status.HTTP_404_NOT_FOUND, REPOSITORY_NOT_FOUND)

    try:
        repository_path = build_repo_path(user_id, repository.local_path_uuid)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, REPOSITORY_NOT_FOUND) from None
    return repository, repository_path


async def pull_owned_repository(
    pg_engine: SQLAlchemyAsyncEngine,
    user_id: str,
    provider: str,
    repo_name: str,
    branch: str,
    auth_environment_loader: Callable[[], Awaitable[dict | None]],
    *,
    expected_local_path_uuid: uuid.UUID | None = None,
) -> bool:
    repository = await get_owned_repository(pg_engine, user_id, provider, repo_name)
    if repository is None or repository.status not in {"pulled", "pulling"}:
        return False
    if (
        expected_local_path_uuid is not None
        and repository.local_path_uuid != expected_local_path_uuid
    ):
        return False
    try:
        build_repo_path(user_id, repository.local_path_uuid)
    except (ValueError, FileNotFoundError):
        return False

    async with clone_repository_lock(user_id, repository.local_path_uuid):
        current = await get_owned_repository(pg_engine, user_id, provider, repo_name)
        if (
            current is None
            or current.status not in {"pulled", "pulling"}
            or current.local_path_uuid != repository.local_path_uuid
        ):
            return False
        try:
            repository_path = build_repo_path(user_id, current.local_path_uuid)
        except (ValueError, FileNotFoundError):
            return False

        updated = await update_owned_repository_status(
            pg_engine,
            user_id,
            current.provider,
            current.repo_name,
            "pulling",
            error_message=None,
        )
        if updated is None:
            return False
        try:
            auth_environment = await auth_environment_loader()
            await pull_repo(repository_path, branch, env=auth_environment)
        except Exception:
            await update_owned_repository_status(
                pg_engine,
                user_id,
                current.provider,
                current.repo_name,
                "pulled",
                error_message="Repository pull failed.",
            )
            raise

        await update_owned_repository_status(
            pg_engine,
            user_id,
            current.provider,
            current.repo_name,
            "pulled",
            error_message=None,
            last_pulled_at=datetime.now(timezone.utc),
        )
        return True


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

    if provider.startswith(GITLAB_PROVIDER_PREFIX):
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


async def list_available_repositories(request: Request, user_id: str):
    all_repositories = []
    github_token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
    if github_token_record:
        try:
            access_token = await decrypt_api_key(github_token_record.access_token)
            if access_token:
                all_repositories.extend(
                    await list_github_repos(
                        access_token, http_client=request.app.state.git_http_client
                    )
                )
        except Exception as exc:
            logger.error("Failed to fetch GitHub repos: %s", exc)

    gitlab_token_records = await get_provider_tokens_by_prefix(
        request.app.state.pg_engine, user_id, GITLAB_PROVIDER_PREFIX
    )
    for token_record in gitlab_token_records:
        try:
            instance_url = get_gitlab_instance_url(token_record.provider)
            tokens = json.loads(token_record.access_token)
            access_token = await decrypt_api_key(tokens["pat"])
            if access_token:
                all_repositories.extend(
                    await list_gitlab_repos(
                        access_token,
                        instance_url,
                        http_client=request.app.state.git_http_client,
                    )
                )
        except Exception as exc:
            logger.error("Failed to fetch GitLab repos for %s: %s", token_record.provider, exc)
    return all_repositories


async def get_repository_branches(request: Request, user_id: str, provider: str, project_path: str):
    repository, repository_path = await _get_owned_ready_repository(
        request, user_id, provider, project_path
    )
    auth_env = await get_git_operation_env(request, user_id, repository.provider)
    return await list_branches(repository_path, env=auth_env)


async def get_repository_tree(
    request: Request, user_id: str, provider: str, project_path: str, branch: str
):
    _, repository_path = await _get_owned_ready_repository(request, user_id, provider, project_path)
    return await build_file_tree_for_branch(repository_path, branch)


async def get_repository_file_content(
    request: Request,
    user_id: str,
    provider: str,
    project_path: str,
    branch: str,
    file_path: str,
):
    _, repository_path = await _get_owned_ready_repository(request, user_id, provider, project_path)
    content = await get_files_content_for_branch(repository_path, branch, [file_path])
    return {"content": content.get(file_path, "")}


async def pull_repository(
    request: Request, user_id: str, provider: str, project_path: str, branch: str
):
    repository = await _get_owned_repository(request, user_id, provider, project_path)

    async def load_auth_environment():
        return await get_git_operation_env(request, user_id, repository.provider)

    pulled = await pull_owned_repository(
        request.app.state.pg_engine,
        user_id,
        repository.provider,
        repository.repo_name,
        branch,
        load_auth_environment,
        expected_local_path_uuid=repository.local_path_uuid,
    )
    if not pulled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, REPOSITORY_NOT_FOUND)
    return {"message": f"Successfully pulled branch '{branch}'."}


async def get_repository_issues(
    request: Request,
    user_id: str,
    provider: str,
    project_path: str,
    state_filter: str,
):
    repository = await _get_owned_repository(request, user_id, provider, project_path)
    if repository.provider.startswith(GITLAB_PROVIDER_PREFIX):
        instance_url = get_gitlab_instance_url(repository.provider)
        token_record = await get_provider_token(
            request.app.state.pg_engine,
            user_id,
            build_gitlab_provider_key(instance_url),
        )
        if not token_record:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                f"GitLab not connected for {instance_url}.",
            )
        tokens = json.loads(token_record.access_token)
        access_token = await decrypt_api_key(tokens["pat"])
        if not access_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitLab token."
            )
        return await list_gitlab_issues(
            access_token,
            instance_url,
            repository.repo_name,
            state_filter,
            http_client=request.app.state.git_http_client,
        )

    token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
    if not token_record:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub not connected.")
    access_token = await decrypt_api_key(token_record.access_token)
    if not access_token:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitHub token."
        )
    return await list_github_issues(
        access_token,
        repository.repo_name,
        state_filter,
        http_client=request.app.state.git_http_client,
    )


async def get_repository_commit_state(
    request: Request,
    user_id: str,
    provider: str,
    project_path: str,
    branch: str,
):
    repository, repository_path = await _get_owned_ready_repository(
        request, user_id, provider, project_path
    )
    if repository.provider.startswith(GITLAB_PROVIDER_PREFIX):
        instance_url = get_gitlab_instance_url(repository.provider)
        token_record = await get_provider_token(
            request.app.state.pg_engine,
            user_id,
            build_gitlab_provider_key(instance_url),
        )
        if not token_record:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                f"GitLab not connected for {instance_url}.",
            )
        tokens = json.loads(token_record.access_token)
        access_token = await decrypt_api_key(tokens["pat"])
        if not access_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitLab token."
            )
        latest_online = await get_latest_online_commit_info_gl(
            instance_url=instance_url,
            project_path=repository.repo_name,
            pat=access_token,
            branch=branch,
            http_client=request.app.state.git_http_client,
        )
    else:
        token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")
        if not token_record:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "GitHub not connected.")
        access_token = await decrypt_api_key(token_record.access_token)
        if not access_token:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt GitHub token."
            )
        latest_online = await get_latest_online_commit_info_gh(
            repo_id=repository.repo_name,
            access_token=access_token,
            branch=branch,
            http_client=request.app.state.git_http_client,
        )

    latest_local = await get_latest_local_commit_info(repository_path, branch)
    return {
        "latest_local": latest_local,
        "latest_online": latest_online,
        "is_up_to_date": latest_local.hash == latest_online.hash,
    }
