import asyncio
import fcntl
import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from services.git_service import CLONED_REPOS_BASE_DIR


def _validated_uuid(value: str | uuid.UUID, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"Invalid {label}.") from exc


def _clone_root() -> Path:
    return CLONED_REPOS_BASE_DIR.resolve(strict=False)


def _user_clone_root_candidate(user_id: str | uuid.UUID) -> Path:
    validated_user_id = _validated_uuid(user_id, "user ID")
    return _clone_root() / str(validated_user_id)


def build_user_clone_root(user_id: str | uuid.UUID) -> Path:
    root = _clone_root()
    user_root_candidate = _user_clone_root_candidate(user_id)
    if user_root_candidate.is_symlink():
        raise ValueError("Invalid user clone path.")
    user_root = user_root_candidate.resolve(strict=False)
    try:
        user_root.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid user clone path.") from exc
    return user_root


def build_repo_path(
    user_id: str | uuid.UUID,
    local_path_uuid: str | uuid.UUID,
    require_git_repo: bool = True,
) -> Path:
    validated_local_uuid = _validated_uuid(local_path_uuid, "repository path ID")
    user_root = build_user_clone_root(user_id)
    repo_path_candidate = user_root / str(validated_local_uuid)
    if repo_path_candidate.is_symlink():
        raise ValueError("Invalid repository clone path.")
    repo_path = repo_path_candidate.resolve(strict=False)
    try:
        repo_path.relative_to(user_root)
    except ValueError as exc:
        raise ValueError("Invalid repository clone path.") from exc

    git_directory = repo_path / ".git"
    if require_git_repo and (
        not repo_path.is_dir() or not git_directory.is_dir() or git_directory.is_symlink()
    ):
        raise FileNotFoundError("Repository not found.")
    return repo_path


@asynccontextmanager
async def clone_repository_lock(user_id: str | uuid.UUID, local_path_uuid: str | uuid.UUID):
    validated_local_uuid = _validated_uuid(local_path_uuid, "repository path ID")
    user_root = build_user_clone_root(user_id)
    user_root.mkdir(parents=True, exist_ok=True)
    lock_root = user_root / ".locks"
    lock_root.mkdir(mode=0o700, exist_ok=True)
    resolved_lock_root = lock_root.resolve(strict=True)
    resolved_lock_root.relative_to(user_root)

    lock_path = resolved_lock_root / f"{validated_local_uuid}.lock"
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    file_descriptor = os.open(lock_path, flags, 0o600)
    lock_file = os.fdopen(file_descriptor, "a+")
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, fcntl.flock, lock_file, fcntl.LOCK_EX)
        yield
    finally:
        await loop.run_in_executor(None, fcntl.flock, lock_file, fcntl.LOCK_UN)
        await loop.run_in_executor(None, lock_file.close)


def create_clone_staging_path(user_id: str | uuid.UUID, local_path_uuid: str | uuid.UUID) -> Path:
    validated_local_uuid = _validated_uuid(local_path_uuid, "repository path ID")
    user_root = build_user_clone_root(user_id)
    user_root.mkdir(parents=True, exist_ok=True)
    staging_root = user_root / ".staging"
    staging_root.mkdir(mode=0o700, exist_ok=True)
    resolved_staging_root = staging_root.resolve(strict=True)
    resolved_staging_root.relative_to(user_root)
    return Path(tempfile.mkdtemp(prefix=f"{validated_local_uuid}-", dir=resolved_staging_root))


def remove_scoped_clone_path(user_id: str | uuid.UUID, path: Path) -> None:
    user_root = build_user_clone_root(user_id)
    resolved_path = path.resolve(strict=False)
    try:
        resolved_path.relative_to(user_root)
    except ValueError as exc:
        raise ValueError("Refusing to remove a path outside the user's clone root.") from exc

    if path.is_symlink():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


async def delete_user_clone_storage(user_id: str | uuid.UUID) -> bool:
    user_root_candidate = _user_clone_root_candidate(user_id)
    try:
        if user_root_candidate.is_symlink():
            user_root_candidate.unlink(missing_ok=True)
        else:
            user_root = build_user_clone_root(user_id)
            if user_root.exists():
                await asyncio.to_thread(shutil.rmtree, user_root)
        return True
    except OSError:
        return False
