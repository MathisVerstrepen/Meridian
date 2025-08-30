import asyncio
import os
from pathlib import Path

from models.github import FileTreeNode

CLONED_REPOS_BASE_DIR = Path(os.path.join("data", "cloned_repos"))


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
    node = FileTreeNode(
        name=name, type="directory", path=relative_path or ".", children=[]
    )

    for item in directory.iterdir():
        if item.name == ".git":  # Skip .git directory
            continue

        item_relative_path = (
            f"{relative_path}/{item.name}" if relative_path else item.name
        )

        if item.is_file():
            node.children.append(
                FileTreeNode(
                    name=item.name, type="file", path=item_relative_path, children=None
                )
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
