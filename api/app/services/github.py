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
