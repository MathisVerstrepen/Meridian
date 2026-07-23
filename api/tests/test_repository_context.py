import asyncio
import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services import node  # noqa: E402


def test_internal_context_skips_non_owned_repository_before_side_effects(monkeypatch):
    request = node.RepoContextRequest(
        branch="main", repo_full_name="owner/private", provider="github"
    )
    calls = []

    monkeypatch.setattr(node, "_parse_github_nodes", lambda *_args: [request])

    async def no_owned_rows(*_args):
        calls.append("lookup")
        return {}

    async def forbidden(*_args, **_kwargs):
        raise AssertionError("repository side effect ran")

    monkeypatch.setattr(node, "get_owned_repositories", no_owned_rows)
    monkeypatch.setattr(node, "_sync_repositories", forbidden)
    monkeypatch.setattr(node, "_fetch_local_file_contents", forbidden)
    monkeypatch.setattr(node, "_fetch_remote_diffs_and_context", forbidden)

    result = asyncio.run(
        node.extract_context_github([], [], True, True, str(uuid.uuid4()), "engine", "http-client")
    )

    assert result == ""
    assert calls == ["lookup"]


def test_internal_auto_pull_uses_owner_uuid_service_and_filters_failed_recheck(monkeypatch):
    local_path_uuid = uuid.uuid4()
    request = node.RepoContextRequest(
        branch="main",
        repo_full_name="owner/private",
        provider="github",
        repo_dir=Path("/scoped/repo"),
        local_path_uuid=local_path_uuid,
    )
    calls = []

    async def pull_owned(
        pg_engine,
        user_id,
        provider,
        repo_name,
        branch,
        auth_loader,
        *,
        expected_local_path_uuid,
    ):
        calls.append(
            (
                pg_engine,
                user_id,
                provider,
                repo_name,
                branch,
                expected_local_path_uuid,
            )
        )
        return False

    monkeypatch.setattr(node, "pull_owned_repository", pull_owned)

    result = asyncio.run(node._sync_repositories([request], "user", "engine"))

    assert result == []
    assert calls == [("engine", "user", "github", "owner/private", "main", local_path_uuid)]
