from pathlib import Path

from services.git_service import CLONED_REPOS_BASE_DIR
from services.gitlab_provider import get_gitlab_storage_provider


def get_storage_provider(provider: str) -> str:
    if provider == "github":
        return provider

    if provider.startswith("gitlab:"):
        return get_gitlab_storage_provider(provider)

    raise ValueError("Unsupported repository provider.")


def build_repo_path(provider: str, project_path: str, require_git_repo: bool = True) -> Path:
    project_path = project_path.strip()
    if not project_path:
        raise ValueError("Repository path cannot be empty.")

    if any(part in {".", ".."} for part in Path(project_path).parts):
        raise ValueError("Invalid repository path.")

    cloned_repos_root = CLONED_REPOS_BASE_DIR.resolve()
    provider_root = (cloned_repos_root / get_storage_provider(provider)).resolve(strict=False)

    provider_root.relative_to(cloned_repos_root)

    path = (provider_root / project_path).resolve(strict=False)
    relative_path = path.relative_to(provider_root)
    if relative_path == Path("."):
        raise ValueError("Invalid repository path.")

    if require_git_repo and (not path.exists() or not (path / ".git").exists()):
        raise FileNotFoundError(f"Repository not found locally at {path}. Please clone it first.")

    return path
