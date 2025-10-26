import asyncio
import fcntl
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sentry_sdk
from models.github import FileTreeNode, GithubCommitInfo

logger = logging.getLogger("uvicorn.error")


CLONED_REPOS_BASE_DIR = Path(os.path.join("data", "cloned_repos"))


@asynccontextmanager
async def repo_lock(repo_dir: Path):
    """Provides an async context manager for a file-based lock on a repo directory."""
    git_dir = repo_dir / ".git"
    if not git_dir.is_dir():
        yield
        return

    lock_file_path = git_dir / "meridian.lock"
    loop = asyncio.get_running_loop()
    lock_file = open(lock_file_path, "a")

    start_time = time.monotonic()
    try:
        with sentry_sdk.start_span(op="lock.acquire", description="git repo lock") as span:
            span.set_tag("lock.type", "file")
            span.set_data("repo_dir", str(repo_dir))
            await loop.run_in_executor(None, fcntl.flock, lock_file, fcntl.LOCK_EX)

            wait_time_ms = (time.monotonic() - start_time) * 1000
            span.set_data("wait_time_ms", wait_time_ms)

        yield
    finally:
        await loop.run_in_executor(None, fcntl.flock, lock_file, fcntl.LOCK_UN)
        await loop.run_in_executor(None, lock_file.close)


async def clone_repo(clone_url: str, target_dir: Path, env: Optional[dict] = None):
    """Clone a Git repository using either HTTPS or SSH."""
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    with sentry_sdk.start_span(op="subprocess.git", description="git clone") as span:
        span.set_tag("git.command", "clone")
        span.set_data("repo_url", clone_url)

        process_env = {**os.environ, **(env or {})}

        process = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            clone_url,
            str(target_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=process_env,
        )

        _, stderr = await process.communicate()
        span.set_data("return_code", process.returncode)

        if process.returncode != 0:
            err_str = stderr.decode(errors="ignore")
            span.set_data("stderr", err_str)
            raise Exception(f"Git clone failed: {err_str}")


async def fetch_repo(target_dir: Path):
    """Fetch the latest changes from a GitHub repository"""
    with sentry_sdk.start_span(op="subprocess.git", description="git fetch") as span:
        span.set_tag("git.command", "fetch")
        span.set_data("repo_dir", str(target_dir))
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
        span.set_data("return_code", process.returncode)

        if process.returncode != 0:
            err_str = stderr.decode(errors="ignore")
            span.set_data("stderr", err_str)
            raise Exception(f"Git fetch failed: {err_str}")


async def pull_repo(target_dir: Path, branch: str, env: Optional[dict] = None):
    """
    Forcefully updates the local repository's working directory to match the
    remote for a specific branch. This is a destructive operation that discards
    any local changes or commits. It is made safe for concurrency by using a lock.
    """
    with sentry_sdk.start_span(op="git.op", description="pull_repo") as span:
        span.set_tag("branch", branch)
        span.set_data("repo_dir", str(target_dir))
        process_env = {**os.environ, **(env or {})}

        async with repo_lock(target_dir):
            # Fetch all latest updates from origin
            await fetch_repo(target_dir)

            # Checkout the desired branch.
            with sentry_sdk.start_span(
                op="subprocess.git", description="git checkout"
            ) as checkout_span:
                checkout_span.set_tag("git.command", "checkout")
                process_checkout = await asyncio.create_subprocess_exec(
                    "git",
                    "-C",
                    str(target_dir),
                    "checkout",
                    branch,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=process_env,
                )
                _, stderr_checkout = await process_checkout.communicate()
                checkout_span.set_data("return_code", process_checkout.returncode)
                if process_checkout.returncode != 0:
                    checkout_span.set_data("stderr", stderr_checkout.decode(errors="ignore"))

            # Hard reset the local branch to match the remote branch.
            with sentry_sdk.start_span(
                op="subprocess.git", description="git reset --hard"
            ) as reset_span:
                reset_span.set_tag("git.command", "reset")
                process_reset = await asyncio.create_subprocess_exec(
                    "git",
                    "-C",
                    str(target_dir),
                    "reset",
                    "--hard",
                    f"origin/{branch}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=process_env,
                )

                _, stderr = await process_reset.communicate()
                reset_span.set_data("return_code", process_reset.returncode)

                if process_reset.returncode != 0:
                    err_str = stderr.decode(errors="ignore")
                    reset_span.set_data("stderr", err_str)
                    raise Exception(f"Git reset --hard failed: {err_str}")


async def list_branches(target_dir: Path) -> list[str]:
    """List all remote branches for a repository, fetching latest updates first."""
    async with repo_lock(target_dir):
        await fetch_repo(target_dir)

        with sentry_sdk.start_span(op="subprocess.git", description="git branch -r") as span:
            span.set_tag("git.command", "branch")
            span.set_data("repo_dir", str(target_dir))
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
            span.set_data("return_code", process.returncode)

            if process.returncode != 0:
                err_str = stderr.decode(errors="ignore")
                span.set_data("stderr", err_str)
                raise Exception(f"Git branch -r failed: {err_str}")

            branches = stdout.decode().strip().split("\n")
            cleaned_branches = [
                branch.replace("origin/", "")
                for branch in branches
                if branch and "origin/HEAD" not in branch
            ]
            span.set_data("branch_count", len(cleaned_branches))
            return cleaned_branches


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
    print(f"Building file tree for branch '{branch}' in repo '{repo_dir}'")
    ref = f"origin/{branch}"
    with sentry_sdk.start_span(op="subprocess.git", description="git ls-tree") as span:
        span.set_tag("git.command", "ls-tree")
        span.set_tag("branch", branch)
        span.set_data("repo_dir", str(repo_dir))
        process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(repo_dir),
            "ls-tree",
            "-r",
            "--full-tree",
            "--name-only",
            "-z",
            ref,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        span.set_data("return_code", process.returncode)

        if process.returncode != 0:
            err_str = stderr.decode(errors="ignore")
            span.set_data("stderr", err_str)
            if "not a valid object name" in err_str:
                raise FileNotFoundError(f"Branch '{branch}' not found in repository.")
            raise Exception(f"Git ls-tree failed: {err_str}")

        paths = stdout.decode().strip("\0").split("\0")
        # Filter out empty strings and .git paths
        paths = [p for p in paths if p and ".git" not in p.split("/")]
        span.set_data("path_count", len(paths))
        return _build_tree_from_paths(paths)


async def get_files_content_for_branch(
    repo_dir: Path, branch: str, file_paths: list[str]
) -> dict[str, str]:
    """
    Get the contents of multiple files from a specific branch using git commands.
    Returns a dictionary mapping file paths to their contents.
    Uses 'git ls-tree' to find blob SHAs and 'git cat-file --batch' to read contents efficiently.
    """
    if not file_paths:
        return {}

    ref = f"origin/{branch}"

    # Path validation
    for path in file_paths:
        if "/.." in path or path.startswith("../") or path.startswith("/"):
            raise PermissionError(f"Invalid file path: {path}")

    with sentry_sdk.start_span(op="subprocess.git", description="git ls-tree + cat-file") as span:
        span.set_tag("git.command", "ls-tree & cat-file")
        span.set_tag("branch", branch)
        span.set_data("file_count", len(file_paths))
        span.set_data("repo_dir", str(repo_dir))

        ls_tree_args = ["git", "-C", str(repo_dir), "ls-tree", "-z", ref, "--"] + file_paths
        ls_tree_process = await asyncio.create_subprocess_exec(
            *ls_tree_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_ls, stderr_ls = await ls_tree_process.communicate()

        if ls_tree_process.returncode != 0:
            err_msg = stderr_ls.decode(errors="ignore")
            span.set_data("stderr_ls_tree", err_msg)
            if "not a valid object name" in err_msg:
                raise FileNotFoundError(f"Branch '{branch}' not found in repository.")
            raise Exception(f"Git ls-tree failed: {err_msg}")

        path_to_sha = {}
        for line in stdout_ls.strip(b"\0").split(b"\0"):
            if not line:
                continue
            meta, path_bytes = line.split(b"\t", 1)
            path = path_bytes.decode(errors="replace")
            _, _, sha_bytes = meta.split(b" ")
            path_to_sha[path] = sha_bytes.decode()

        found_files = set(path_to_sha.keys())
        requested_files = set(file_paths)
        if not found_files == requested_files:
            missing_files = requested_files - found_files
            logger.warning(f"File(s) not found in branch '{branch}': {', '.join(missing_files)}")
            sentry_sdk.capture_message(
                f"Warning: File(s) not found in branch '{branch}': {', '.join(missing_files)}",
                level="warning",
            )
            for missing in missing_files:
                path_to_sha.pop(missing, None)

        if not path_to_sha:
            return {}

        cat_file_process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(repo_dir),
            "cat-file",
            "--batch",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        shas_to_read = "\n".join(path_to_sha.values()).encode()
        stdout_cat, stderr_cat = await cat_file_process.communicate(input=shas_to_read)

        if cat_file_process.returncode != 0:
            err_msg = stderr_cat.decode(errors="ignore")
            span.set_data("stderr_cat_file", err_msg)
            raise Exception(f"Git cat-file failed: {err_msg}")

        sha_to_path = {v: k for k, v in path_to_sha.items()}
        file_contents = {}
        output_stream = stdout_cat
        while output_stream:
            header_line, rest = output_stream.split(b"\n", 1)
            sha, _, size_str = header_line.decode().split(" ")
            size = int(size_str)

            content_bytes = rest[:size]
            output_stream = rest[size + 1 :]

            path = sha_to_path[sha]
            file_contents[path] = content_bytes.decode(errors="replace")

        return file_contents


async def get_latest_local_commit_info(repo_dir: Path, branch: str) -> GithubCommitInfo:
    """Get the latest commit information for a specific branch"""
    ref = f"origin/{branch}"
    with sentry_sdk.start_span(op="subprocess.git", description="git log -1") as span:
        span.set_tag("git.command", "log")
        span.set_tag("branch", branch)
        span.set_data("repo_dir", str(repo_dir))
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
        span.set_data("return_code", process.returncode)

        if process.returncode != 0:
            err_str = stderr.decode(errors="ignore")
            span.set_data("stderr", err_str)
            raise Exception(f"Git log failed: {err_str}")

        commit_info_parts = stdout.decode().strip().split("|")
        local_date = datetime.strptime(commit_info_parts[2], "%Y-%m-%d %H:%M:%S %z")

        commit_info = GithubCommitInfo(
            hash=commit_info_parts[0],
            author=commit_info_parts[1],
            date=local_date.astimezone(timezone.utc),
        )
        span.set_data("commit_hash", commit_info.hash)
        return commit_info
