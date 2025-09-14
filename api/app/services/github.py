import asyncio
import fcntl
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
import sentry_sdk
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
    loop = asyncio.get_running_loop()
    lock_file = open(lock_file_path, "a")

    start_time = time.monotonic()
    try:
        with sentry_sdk.start_span(op="lock.acquire", description="git repo lock") as span:
            span.set_tag("lock.type", "file")
            span.set_data("repo_dir", str(repo_dir))
            await loop.run_in_executor(None, fcntl.flock, lock_file, fcntl.LOCK_EX)

            wait_time_ms = (time.monotonic() - start_time) * 1000
            sentry_sdk.metrics.distribution("git.lock.wait_time", wait_time_ms, unit="millisecond")
            span.set_data("wait_time_ms", wait_time_ms)

        yield
    finally:
        await loop.run_in_executor(None, fcntl.flock, lock_file, fcntl.LOCK_UN)
        await loop.run_in_executor(None, lock_file.close)


async def get_github_access_token(request, user_id: str) -> str:
    """
    Retrieves the GitHub access token for the specified user.
    """
    with sentry_sdk.start_span(op="github.auth", description="get_github_access_token"):
        token_record = await get_provider_token(request.app.state.pg_engine, user_id, "github")

        if not token_record:
            sentry_sdk.capture_message("GitHub token not found for user", level="warning")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub account is not connected.",
            )

        with sentry_sdk.start_span(op="crypto.decrypt", description="decrypt_api_key"):
            access_token = decrypt_api_key(token_record.access_token)

        if not access_token:
            sentry_sdk.capture_message("Failed to decrypt GitHub token", level="error")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="GitHub access token is invalid.",
            )

        return access_token


async def clone_repo(owner: str, repo: str, token: str, target_dir: Path):
    """Clone a GitHub repository using the provided token"""
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    repo_url = f"https://{token}@github.com/{owner}/{repo}.git"

    with sentry_sdk.start_span(op="subprocess.git", description="git clone") as span:
        span.set_tag("git.command", "clone")
        span.set_data("repo", f"{owner}/{repo}")

        process = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            repo_url,
            str(target_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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


async def pull_repo(target_dir: Path, branch: str):
    """
    Forcefully updates the local repository's working directory to match the
    remote for a specific branch. This is a destructive operation that discards
    any local changes or commits. It is made safe for concurrency by using a lock.
    """
    with sentry_sdk.start_span(op="git.op", description="pull_repo") as span:
        span.set_tag("branch", branch)
        span.set_data("repo_dir", str(target_dir))
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
                )

                _, stderr = await process_reset.communicate()
                reset_span.set_data("return_code", process_reset.returncode)

                if process_reset.returncode != 0:
                    err_str = stderr.decode(errors="ignore")
                    reset_span.set_data("stderr", err_str)
                    raise Exception(f"Git reset --hard failed: {err_str}")


async def list_branches(target_dir: Path) -> list[str]:
    """List all remote branches for a repository"""
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


async def get_default_branch(target_dir: Path) -> str:
    """Get the default branch name for the repository"""
    with sentry_sdk.start_span(op="git.op", description="get_default_branch") as span:
        span.set_data("repo_dir", str(target_dir))
        # Get the current branch name
        with sentry_sdk.start_span(op="subprocess.git", description="git rev-parse") as rev_span:
            rev_span.set_tag("git.command", "rev-parse")
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
            rev_span.set_data("return_code", process.returncode)

            if process.returncode == 0:
                return stdout.decode().strip()

        # Fallback: try to get the default branch from remote
        with sentry_sdk.start_span(op="subprocess.git", description="git symbolic-ref") as sym_span:
            sym_span.set_tag("git.command", "symbolic-ref")
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
            sym_span.set_data("return_code", process.returncode)

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


def get_file_content(file_path: Path) -> str:
    """Get the content of a file ensuring it's inside CLONED_REPOS_BASE_DIR"""
    with sentry_sdk.start_span(op="file.read", description="get_file_content") as span:
        span.set_data("file_path", str(file_path))
        base = CLONED_REPOS_BASE_DIR.resolve()
        try:
            resolved = file_path.resolve(strict=True)
            span.set_data("resolved_path", str(resolved))
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
        file_size = resolved.stat().st_size
        span.set_data("file_size", file_size)
        if file_size > max_size:
            raise ValueError("File is too large to be read")

        with resolved.open("r", encoding="utf-8", errors="replace") as f:
            return f.read()


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

        # 1. Use ls-tree to find the blob SHAs for all requested file paths.
        # The -z flag uses NUL characters to terminate output, handling special filenames.
        # The `--` separates paths from other options for safety.
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
        # Output is NUL-separated: <mode> <type> <sha>\t<path>\0
        for line in stdout_ls.strip(b"\0").split(b"\0"):
            if not line:
                continue
            meta, path_bytes = line.split(b"\t", 1)
            path = path_bytes.decode(errors="replace")
            _, _, sha_bytes = meta.split(b" ")
            path_to_sha[path] = sha_bytes.decode()

        # Check for files not found by ls-tree, which doesn't error for non-existent paths.
        found_files = set(path_to_sha.keys())
        requested_files = set(file_paths)
        if not found_files == requested_files:
            missing_files = requested_files - found_files
            raise FileNotFoundError(
                f"File(s) not found in branch '{branch}': {', '.join(missing_files)}"
            )

        if not path_to_sha:
            return {}

        # 2. Use cat-file --batch to get the content of all blobs
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

        # 3. Parse the output of cat-file
        sha_to_path = {v: k for k, v in path_to_sha.items()}
        file_contents = {}
        output_stream = stdout_cat
        while output_stream:
            # Format: <sha> <type> <size>\n<contents>\n
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


async def get_latest_online_commit_info(
    repo_id: str, access_token: str, branch: str
) -> GithubCommitInfo:
    """Get the latest commit information for a specific branch of a GitHub repository"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Meridian Github Connector",
    }
    sentry_sdk.add_breadcrumb(
        category="github.api",
        message=f"Fetching latest online commit for {repo_id}",
        level="info",
        data={"branch": branch},
    )
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
