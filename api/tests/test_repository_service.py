import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.repository_ops import repository_crud  # noqa: E402
from services import repository_clone_service, repository_paths, repository_service  # noqa: E402


def _request():
    state = SimpleNamespace(pg_engine="engine", git_http_client="http-client")
    return SimpleNamespace(app=SimpleNamespace(state=state))


def test_repository_lookup_query_is_owner_qualified(monkeypatch):
    repository = SimpleNamespace()

    class Result:
        def scalar_one_or_none(self):
            return repository

    class Session:
        statement = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def exec(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    monkeypatch.setattr(repository_crud, "AsyncSession", lambda _engine: session)
    user_id = str(uuid.uuid4())

    result = asyncio.run(
        repository_crud.get_owned_repository("engine", user_id, "github", "owner/repo")
    )
    compiled = session.statement.compile()

    assert result is repository
    assert "repositories.user_id" in str(compiled)
    assert "repositories.provider" in str(compiled)
    assert "repositories.repo_name" in str(compiled)
    assert {user_id, "github", "owner/repo"}.issubset(set(compiled.params.values()))


def test_stored_clone_urls_are_credential_free():
    assert (
        repository_clone_service._credential_free_clone_url(
            "https://token@example.com/owner/repo.git?private=1"
        )
        == "https://example.com/owner/repo.git"
    )
    assert (
        repository_clone_service._credential_free_clone_url(
            "ssh://git:secret@example.com/owner/repo.git?private=1"
        )
        == "ssh://git@example.com/owner/repo.git"
    )


@pytest.mark.parametrize(
    "operation,args",
    [
        (repository_service.get_repository_branches, ()),
        (repository_service.get_repository_tree, ("main",)),
        (repository_service.get_repository_file_content, ("main", "README.md")),
        (repository_service.pull_repository, ("main",)),
        (repository_service.get_repository_issues, ("open",)),
        (repository_service.get_repository_commit_state, ("main",)),
    ],
)
def test_non_owner_is_rejected_before_target_side_effects(monkeypatch, operation, args):
    calls = []

    async def no_owned_row(*_args):
        calls.append("lookup")
        return None

    async def forbidden_side_effect(*_args, **_kwargs):
        raise AssertionError("side effect ran before authorization")

    monkeypatch.setattr(repository_service, "get_owned_repository", no_owned_row)
    for name in (
        "get_provider_token",
        "list_branches",
        "build_file_tree_for_branch",
        "get_files_content_for_branch",
        "pull_repo",
        "list_github_issues",
        "get_latest_local_commit_info",
    ):
        monkeypatch.setattr(repository_service, name, forbidden_side_effect)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(operation(_request(), str(uuid.uuid4()), "github", "owner/repo", *args))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Repository not found."
    assert calls == ["lookup"]


def test_owned_issues_do_not_require_local_clone_readiness(monkeypatch):
    repository = SimpleNamespace(
        provider="github",
        repo_name="owner/repo",
        local_path_uuid=uuid.uuid4(),
        status="unpulled",
    )
    token_record = SimpleNamespace(access_token="encrypted")
    calls = []

    async def get_row(*_args):
        calls.append("owner")
        return repository

    async def get_token(*_args):
        calls.append("credentials")
        return token_record

    async def decrypt(_token):
        return "token"

    async def list_issues(*_args, **_kwargs):
        calls.append("provider")
        return ["issue"]

    monkeypatch.setattr(repository_service, "get_owned_repository", get_row)
    monkeypatch.setattr(repository_service, "get_provider_token", get_token)
    monkeypatch.setattr(repository_service, "decrypt_api_key", decrypt)
    monkeypatch.setattr(repository_service, "list_github_issues", list_issues)
    monkeypatch.setattr(
        repository_service,
        "build_repo_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("filesystem lookup")),
    )

    result = asyncio.run(
        repository_service.get_repository_issues(
            _request(), str(uuid.uuid4()), "github", "owner/repo", "open"
        )
    )

    assert result == ["issue"]
    assert calls == ["owner", "credentials", "provider"]


def test_pull_serializes_by_owner_row_uuid_and_rechecks_inside_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", tmp_path)
    user_id = uuid.uuid4()
    repository = SimpleNamespace(
        provider="github",
        repo_name="owner/repo",
        local_path_uuid=uuid.uuid4(),
        status="pulled",
        error_message=None,
    )
    (tmp_path / str(user_id) / str(repository.local_path_uuid) / ".git").mkdir(parents=True)
    lookups = 0
    active_pulls = 0
    maximum_active_pulls = 0

    async def get_row(*_args):
        nonlocal lookups
        lookups += 1
        return repository

    async def update_status(*args, **kwargs):
        repository.status = args[4]
        repository.error_message = kwargs["error_message"]
        return repository

    async def load_auth():
        return None

    async def fake_pull(*_args, **_kwargs):
        nonlocal active_pulls, maximum_active_pulls
        active_pulls += 1
        maximum_active_pulls = max(maximum_active_pulls, active_pulls)
        await asyncio.sleep(0.01)
        active_pulls -= 1

    monkeypatch.setattr(repository_service, "get_owned_repository", get_row)
    monkeypatch.setattr(repository_service, "update_owned_repository_status", update_status)
    monkeypatch.setattr(repository_service, "pull_repo", fake_pull)

    async def run_pulls():
        return await asyncio.gather(
            repository_service.pull_owned_repository(
                "engine",
                str(user_id),
                "github",
                "owner/repo",
                "main",
                load_auth,
                expected_local_path_uuid=repository.local_path_uuid,
            ),
            repository_service.pull_owned_repository(
                "engine",
                str(user_id),
                "github",
                "owner/repo",
                "main",
                load_auth,
                expected_local_path_uuid=repository.local_path_uuid,
            ),
        )

    assert asyncio.run(run_pulls()) == [True, True]
    assert maximum_active_pulls == 1
    assert lookups >= 4
    assert repository.status == "pulled"


def _configure_clone_fakes(monkeypatch, row):
    async def reserve(*_args):
        return row

    async def get_row(*_args):
        return row

    async def update_url(*_args):
        return row

    async def update_status(*args, **kwargs):
        row.status = args[4]
        row.error_message = kwargs["error_message"]
        return row

    async def no_auth(*_args):
        return None

    monkeypatch.setattr(repository_clone_service, "reserve_owned_repository", reserve)
    monkeypatch.setattr(repository_clone_service, "get_owned_repository", get_row)
    monkeypatch.setattr(repository_clone_service, "update_owned_repository_clone_url", update_url)
    monkeypatch.setattr(repository_clone_service, "update_owned_repository_status", update_status)
    monkeypatch.setattr(repository_clone_service, "get_git_operation_env", no_auth)


def test_concurrent_same_user_clone_publishes_once(monkeypatch, tmp_path):
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", tmp_path)
    user_id = uuid.uuid4()
    row = SimpleNamespace(
        provider="github",
        repo_name="owner/repo",
        local_path_uuid=uuid.uuid4(),
        status="unpulled",
        error_message=None,
    )
    _configure_clone_fakes(monkeypatch, row)
    clone_calls = 0

    async def fake_clone(_url, target, env=None):
        nonlocal clone_calls
        clone_calls += 1
        await asyncio.sleep(0.01)
        (target / ".git").mkdir()

    monkeypatch.setattr(repository_clone_service, "clone_repo", fake_clone)

    async def run_clones():
        return await asyncio.gather(
            repository_clone_service.clone_repository(
                _request(), str(user_id), "github", "owner/repo", "https://example/repo", "https"
            ),
            repository_clone_service.clone_repository(
                _request(), str(user_id), "github", "owner/repo", "https://example/repo", "https"
            ),
        )

    responses = asyncio.run(run_clones())

    assert clone_calls == 1
    assert {response["message"] for response in responses} == {
        "Repository cloned successfully.",
        "Repository already cloned.",
    }
    assert (tmp_path / str(user_id) / str(row.local_path_uuid) / ".git").is_dir()


def test_two_users_same_repository_get_distinct_rows_and_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", tmp_path)
    rows = {}

    async def reserve(_engine, user_id, provider, repo_name, clone_url):
        rows.setdefault(
            user_id,
            SimpleNamespace(
                provider=provider,
                repo_name=repo_name,
                local_path_uuid=uuid.uuid4(),
                status="unpulled",
                error_message=None,
                clone_url=clone_url,
            ),
        )
        return rows[user_id]

    async def get_row(_engine, user_id, *_args):
        return rows[user_id]

    async def update_url(_engine, user_id, *_args):
        return rows[user_id]

    async def update_status(_engine, user_id, _provider, _repo_name, status_value, **kwargs):
        rows[user_id].status = status_value
        rows[user_id].error_message = kwargs["error_message"]
        return rows[user_id]

    async def no_auth(*_args):
        return None

    async def fake_clone(_url, target, env=None):
        (target / ".git").mkdir()

    monkeypatch.setattr(repository_clone_service, "reserve_owned_repository", reserve)
    monkeypatch.setattr(repository_clone_service, "get_owned_repository", get_row)
    monkeypatch.setattr(repository_clone_service, "update_owned_repository_clone_url", update_url)
    monkeypatch.setattr(repository_clone_service, "update_owned_repository_status", update_status)
    monkeypatch.setattr(repository_clone_service, "get_git_operation_env", no_auth)
    monkeypatch.setattr(repository_clone_service, "clone_repo", fake_clone)
    first_user = str(uuid.uuid4())
    second_user = str(uuid.uuid4())

    async def clone_for_both_users():
        return await asyncio.gather(
            repository_clone_service.clone_repository(
                _request(), first_user, "github", "owner/repo", "https://example/repo", "https"
            ),
            repository_clone_service.clone_repository(
                _request(), second_user, "github", "owner/repo", "https://example/repo", "https"
            ),
        )

    first, second = asyncio.run(clone_for_both_users())

    assert rows[first_user] is not rows[second_user]
    assert rows[first_user].local_path_uuid != rows[second_user].local_path_uuid
    assert first["path"] == str(tmp_path / first_user / str(rows[first_user].local_path_uuid))
    assert second["path"] == str(tmp_path / second_user / str(rows[second_user].local_path_uuid))


def test_clone_failure_retries_same_uuid_and_leaves_legacy_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", tmp_path)
    user_id = uuid.uuid4()
    row = SimpleNamespace(
        provider="github",
        repo_name="owner/repo",
        local_path_uuid=uuid.uuid4(),
        status="unpulled",
        error_message=None,
    )
    _configure_clone_fakes(monkeypatch, row)
    legacy_marker = tmp_path / "github" / "owner" / "repo" / "marker"
    legacy_marker.parent.mkdir(parents=True)
    legacy_marker.write_text("untouched")
    attempts = 0

    async def flaky_clone(_url, target, env=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("token=https://secret@example.invalid")
        (target / ".git").mkdir()

    monkeypatch.setattr(repository_clone_service, "clone_repo", flaky_clone)
    call = lambda: repository_clone_service.clone_repository(  # noqa: E731
        _request(), str(user_id), "github", "owner/repo", "https://example/repo", "https"
    )

    with pytest.raises(RuntimeError):
        asyncio.run(call())
    assert row.status == "error"
    response = asyncio.run(call())

    assert response["path"] == str(tmp_path / str(user_id) / str(row.local_path_uuid))
    assert row.status == "pulled"
    assert legacy_marker.read_text() == "untouched"
