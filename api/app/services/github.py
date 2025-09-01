import asyncio
import os
import httpx
from pathlib import Path

from models.github import FileTreeNode, GithubCommitInfo

CLONED_REPOS_BASE_DIR = Path(os.path.join("data", "cloned_repos"))

from database.pg.token_ops.provider_token_crud import (
    get_provider_token,
)
from services.crypto import decrypt_api_key
from fastapi import HTTPException, status
from datetime import timezone, datetime


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


async def pull_repo(target_dir: Path):
    """Pull the latest changes from a GitHub repository"""
    default_branch = await get_default_branch(target_dir)

    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(target_dir),
        "pull",
        "origin",
        default_branch,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Git pull failed: {stderr.decode()}")


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


async def get_latest_local_commit_info(repo_dir: Path) -> GithubCommitInfo:
    """Get the latest commit information for a GitHub repository"""
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(repo_dir),
        "log",
        "-1",
        "--pretty=format:%H|%an|%ai",
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


async def get_latest_online_commit_info(repo_id: str, access_token: str) -> GithubCommitInfo:
    """Get the latest commit information for a GitHub repository"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Meridian Github Connector",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo_id}/commits?per_page=1",
            headers=headers,
        )

    if response.status_code != 200:
        raise Exception(f"GitHub API request failed: {response.text}")

    commit_info = response.json()[0]

    return GithubCommitInfo(
        hash=commit_info["sha"],
        author=commit_info["commit"]["author"]["name"],
        date=datetime.fromisoformat(commit_info["commit"]["author"]["date"]),
    )
