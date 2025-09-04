import asyncio
import fcntl
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from database.pg.token_ops.provider_token_crud import get_provider_token
from fastapi import HTTPException, status
from models.github import FileTreeNode, GithubCommitInfo
from services.crypto import decrypt_api_key

CLONED_REPOS_BASE_DIR = Path(os.path.join("data", "cloned_repos"))


@asynccontextmanager
async def repo_lock(repo_dir: Path):
    """Provides an async context manager for a file-based lock on a repo directory."""
    git_dir = repo_dir / ".git"
    if not git_dir.is_dir():
        yield
        return

    lock_file_path = git_dir / "meridian.lock"
    lock_file = open(lock_file_path, "a")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


async def get_github_access_token(request, user_id: str) -> str:
    """
    Retrieves the GitHub access token for the specified user.
    """
    token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub account is not connected.",
        )

    access_token = decrypt_api_key(token_record.access_token)

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub access token is invalid.",
        )

    return access_token


async def clone_repo(owner: str, repo: str, token: str, target_dir: Path):
    """Clone a GitHub repository using the provided token"""
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    repo_url = f"https://{token}@github.com/{owner}/{repo}.git"

    process = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        repo_url,
        str(target_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Git clone failed: {stderr.decode()}")


async def fetch_repo(target_dir: Path):
    """Fetch the latest changes from a GitHub repository"""
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(target_dir),
        "fetch",
        "origin",
        "--prune",
        "--force",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Git fetch failed: {stderr.decode()}")


async def pull_repo(target_dir: Path, branch: str):
    """
    Forcefully updates the local repository's working directory to match the
    remote for a specific branch. This is a destructive operation that discards
    any local changes or commits. It is made safe for concurrency by using a lock.
    """
    async with repo_lock(target_dir):
        # Fetch all latest updates from origin
        await fetch_repo(target_dir)

        # Checkout the desired branch.
        process_checkout = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(target_dir),
            "checkout",
            branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process_checkout.communicate()

        # Hard reset the local branch to match the remote branch.
        process_reset = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(target_dir),
            "reset",
            "--hard",
            f"origin/{branch}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process_reset.communicate()

        if process_reset.returncode != 0:
            raise Exception(f"Git reset --hard failed: {stderr.decode()}")


async def list_branches(target_dir: Path) -> list[str]:
    """List all remote branches for a repository"""
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(target_dir),
        "branch",
        "-r",
        "--format=%(refname:short)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Git branch -r failed: {stderr.decode()}")

    branches = stdout.decode().strip().split("\n")
    cleaned_branches = [
        branch.replace("origin/", "")
        for branch in branches
        if branch and "origin/HEAD" not in branch
    ]
    return cleaned_branches


async def get_default_branch(target_dir: Path) -> str:
    """Get the default branch name for the repository"""
    # Get the current branch name
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(target_dir),
        "rev-parse",
        "--abbrev-ref",
        "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        return stdout.decode().strip()

    # Fallback: try to get the default branch from remote
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(target_dir),
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        return stdout.decode().strip().split("/")[-1]

    return "main"


def build_file_tree(directory: Path, relative_path: str = "") -> FileTreeNode:
    """Recursively build a file tree structure from a directory"""
    name = directory.name if relative_path else "root"
    node = FileTreeNode(name=name, type="directory", path=relative_path or ".", children=[])

    for item in directory.iterdir():
        if item.name == ".git":  # Skip .git directory
            continue

        item_relative_path = f"{relative_path}/{item.name}" if relative_path else item.name

        if item.is_file():
            node.children.append(
                FileTreeNode(name=item.name, type="file", path=item_relative_path, children=[])
            )
        elif item.is_dir():
            node.children.append(build_file_tree(item, item_relative_path))

    # Sort directories first, then files
    node.children.sort(key=lambda x: (x.type != "directory", x.name.lower()))

    return node


def _build_tree_from_paths(paths: list[str]) -> FileTreeNode:
    root = FileTreeNode(name="root", type="directory", path=".", children=[])

    for path_str in paths:
        parts = path_str.split("/")
        current_level_nodes = root.children
        current_path_parts = []

        for i, part in enumerate(parts):
            current_path_parts.append(part)
            full_path = "/".join(current_path_parts)

            existing_node = next((n for n in current_level_nodes if n.name == part), None)

            if not existing_node:
                is_file = i == len(parts) - 1
                node_type = "file" if is_file else "directory"

                new_node = FileTreeNode(name=part, type=node_type, path=full_path, children=[])
                current_level_nodes.append(new_node)
                current_level_nodes = new_node.children
            else:
                current_level_nodes = existing_node.children

    def sort_children(node: FileTreeNode):
        node.children.sort(key=lambda x: (x.type != "directory", x.name.lower()))
        for child in node.children:
            if child.type == "directory":
                sort_children(child)

    sort_children(root)
    return root


async def build_file_tree_for_branch(repo_dir: Path, branch: str) -> FileTreeNode:
    """Build a file tree structure from a specific branch using git ls-tree"""
    ref = f"origin/{branch}"
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo_dir),
        "ls-tree",
        "-r",
        "--full-tree",
        "--name-only",
        ref,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        if "not a valid object name" in stderr.decode():
            raise FileNotFoundError(f"Branch '{branch}' not found in repository.")
        raise Exception(f"Git ls-tree failed: {stderr.decode()}")

    paths = stdout.decode().strip().split("\n")
    # Filter out empty strings and .git paths
    paths = [p for p in paths if p and ".git" not in p.split("/")]
    return _build_tree_from_paths(paths)


def get_file_content(file_path: Path) -> str:
    """Get the content of a file ensuring it's inside CLONED_REPOS_BASE_DIR"""
    base = CLONED_REPOS_BASE_DIR.resolve()
    try:
        resolved = file_path.resolve(strict=True)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")

    # Ensure path is under allowed base directory
    try:
        resolved.relative_to(base)
    except ValueError:
        raise PermissionError("Access to the requested path is not allowed")

    # Disallow .git entries
    if ".git" in resolved.parts:
        raise PermissionError("Access to .git directories is not allowed")

    if not resolved.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    # Protect against extremely large files
    max_size = 5 * 1024 * 1024  # 5 MB
    if resolved.stat().st_size > max_size:
        raise ValueError("File is too large to be read")

    with resolved.open("r", encoding="utf-8", errors="replace") as f:
        return f.read()


async def get_file_content_for_branch(repo_dir: Path, branch: str, file_path: str) -> str:
    """Get the content of a file from a specific branch without checkout"""
    ref = f"origin/{branch}:{file_path}"

    # Basic path validation to prevent command injection
    if ".." in file_path or file_path.startswith("/"):
        raise PermissionError("Invalid file path")

    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo_dir),
        "show",
        ref,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        err_msg = stderr.decode()
        if (
            f"exists on disk, but not in 'origin/{branch}'" in err_msg
            or "Invalid object name" in err_msg
        ):
            raise FileNotFoundError(f"File '{file_path}' not found in branch '{branch}'.")
        raise Exception(f"Git show failed: {err_msg}")

    return stdout.decode(errors="replace")


async def get_latest_local_commit_info(repo_dir: Path, branch: str) -> GithubCommitInfo:
    """Get the latest commit information for a specific branch"""
    ref = f"origin/{branch}"
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo_dir),
        "log",
        "-1",
        "--pretty=format:%H|%an|%ai",
        ref,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Git log failed: {stderr.decode()}")

    commit_info = stdout.decode().strip().split("|")
    local_date = datetime.strptime(commit_info[2], "%Y-%m-%d %H:%M:%S %z")

    return GithubCommitInfo(
        hash=commit_info[0],
        author=commit_info[1],
        date=local_date.astimezone(timezone.utc),
    )


async def get_latest_online_commit_info(
    repo_id: str, access_token: str, branch: str
) -> GithubCommitInfo:
    """Get the latest commit information for a specific branch of a GitHub repository"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Meridian Github Connector",
    }
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
