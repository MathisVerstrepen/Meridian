import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

from database.pg.repository_ops.repository_crud import (
    get_owned_repository,
    reserve_owned_repository,
    update_owned_repository_clone_url,
    update_owned_repository_status,
)
from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import HTTPException, Request, status
from services.crypto import decrypt_api_key
from services.git_service import clone_repo, sanitize_git_url
from services.gitlab_provider import build_gitlab_provider_key, get_gitlab_instance_url
from services.repository_paths import (
    build_repo_path,
    clone_repository_lock,
    create_clone_staging_path,
    remove_scoped_clone_path,
)
from services.repository_service import canonicalize_repository_identity, get_git_operation_env
from services.ssh_manager import ssh_key_context


def _credential_free_clone_url(clone_url: str) -> str:
    sanitized_url = sanitize_git_url(clone_url)
    parsed = urlsplit(sanitized_url)
    if parsed.scheme != "ssh" or not parsed.hostname:
        return sanitized_url
    netloc = f"{parsed.username}@{parsed.hostname}" if parsed.username else parsed.hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


@asynccontextmanager
async def _clone_auth_environment(
    request: Request,
    user_id: str,
    provider: str,
    clone_method: str,
) -> AsyncIterator[dict | None]:
    if clone_method == "https":
        yield await get_git_operation_env(request, user_id, provider)
        return

    if clone_method != "ssh":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported clone method.")
    if not provider.startswith("gitlab:"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "SSH cloning not configured for this provider."
        )

    token_record = await get_provider_token(
        request.app.state.pg_engine,
        user_id,
        build_gitlab_provider_key(get_gitlab_instance_url(provider)),
    )
    if not token_record:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"No credentials found for provider {provider}.",
        )
    tokens = json.loads(token_record.access_token)
    ssh_key = await decrypt_api_key(tokens["ssh_key"])
    if not ssh_key:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to decrypt key.")
    async with ssh_key_context(ssh_key) as environment:
        yield environment


async def clone_repository(
    request: Request,
    user_id: str,
    provider: str,
    full_name: str,
    clone_url: str,
    clone_method: str,
) -> dict[str, str]:
    provider, full_name = canonicalize_repository_identity(provider, full_name)
    if clone_method not in {"https", "ssh"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported clone method.")
    if clone_method == "ssh" and not provider.startswith("gitlab:"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "SSH cloning not configured for this provider."
        )

    safe_clone_url = _credential_free_clone_url(clone_url)
    repository = await reserve_owned_repository(
        request.app.state.pg_engine,
        user_id,
        provider,
        full_name,
        safe_clone_url,
    )
    updated_repository = await update_owned_repository_clone_url(
        request.app.state.pg_engine,
        user_id,
        provider,
        full_name,
        safe_clone_url,
    )
    if updated_repository is not None:
        repository = updated_repository

    async with clone_repository_lock(user_id, repository.local_path_uuid):
        current = await get_owned_repository(
            request.app.state.pg_engine, user_id, provider, full_name
        )
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found.")

        try:
            target_path = build_repo_path(user_id, current.local_path_uuid, require_git_repo=False)
        except ValueError:
            await update_owned_repository_status(
                request.app.state.pg_engine,
                user_id,
                provider,
                full_name,
                "error",
                error_message="Repository storage requires manual recovery.",
            )
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Repository storage requires recovery."
            ) from None
        target_git_directory = target_path / ".git"
        if (
            target_path.is_dir()
            and target_git_directory.is_dir()
            and not target_git_directory.is_symlink()
        ):
            await update_owned_repository_status(
                request.app.state.pg_engine,
                user_id,
                provider,
                full_name,
                "pulled",
                error_message=None,
                last_pulled_at=datetime.now(timezone.utc),
            )
            return {"message": "Repository already cloned.", "path": str(target_path)}
        if target_path.exists() or target_path.is_symlink():
            await update_owned_repository_status(
                request.app.state.pg_engine,
                user_id,
                provider,
                full_name,
                "error",
                error_message="Repository storage requires manual recovery.",
            )
            raise HTTPException(status.HTTP_409_CONFLICT, "Repository storage requires recovery.")

        await update_owned_repository_status(
            request.app.state.pg_engine,
            user_id,
            provider,
            full_name,
            "pulling",
            error_message=None,
        )
        staging_path = create_clone_staging_path(user_id, current.local_path_uuid)
        published = False
        try:
            async with _clone_auth_environment(
                request, user_id, provider, clone_method
            ) as environment:
                await clone_repo(clone_url, staging_path, env=environment)
            staging_git_directory = staging_path / ".git"
            if not staging_git_directory.is_dir() or staging_git_directory.is_symlink():
                raise RuntimeError("Clone did not produce a valid Git repository.")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging_path, target_path)
            published = True
            await update_owned_repository_status(
                request.app.state.pg_engine,
                user_id,
                provider,
                full_name,
                "pulled",
                error_message=None,
                last_pulled_at=datetime.now(timezone.utc),
            )
        except Exception:
            remove_scoped_clone_path(user_id, staging_path)
            if published:
                remove_scoped_clone_path(user_id, target_path)
            await update_owned_repository_status(
                request.app.state.pg_engine,
                user_id,
                provider,
                full_name,
                "error",
                error_message="Repository clone failed.",
            )
            raise

        message = (
            "Repository cloned successfully via SSH."
            if clone_method == "ssh"
            else "Repository cloned successfully."
        )
        return {"message": message, "path": str(target_path)}
