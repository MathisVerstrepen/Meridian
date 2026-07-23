import asyncio
import sys
import uuid
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services import repository_paths  # noqa: E402


def test_repository_paths_use_only_user_and_repository_uuids(monkeypatch, tmp_path):
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", tmp_path)
    user_id = uuid.uuid4()
    repository_id = uuid.uuid4()

    path = repository_paths.build_repo_path(user_id, repository_id, require_git_repo=False)

    assert path == tmp_path / str(user_id) / str(repository_id)
    with pytest.raises(ValueError):
        repository_paths.build_repo_path("../user", repository_id, require_git_repo=False)
    with pytest.raises(ValueError):
        repository_paths.build_repo_path(user_id, "../repo", require_git_repo=False)

    other_user_path = repository_paths.build_repo_path(
        uuid.uuid4(), uuid.uuid4(), require_git_repo=False
    )
    assert other_user_path != path


def test_repository_path_rejects_symlink_escape(monkeypatch, tmp_path):
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", tmp_path / "clones")
    user_id = uuid.uuid4()
    repository_id = uuid.uuid4()
    user_root = tmp_path / "clones" / str(user_id)
    user_root.mkdir(parents=True)
    (user_root / str(repository_id)).symlink_to(tmp_path / "outside", target_is_directory=True)

    with pytest.raises(ValueError):
        repository_paths.build_repo_path(user_id, repository_id, require_git_repo=False)


def test_delete_user_clone_storage_preserves_siblings_and_legacy(monkeypatch, tmp_path):
    clone_root = tmp_path / "clones"
    monkeypatch.setattr(repository_paths, "CLONED_REPOS_BASE_DIR", clone_root)
    target_user = uuid.uuid4()
    sibling_user = uuid.uuid4()
    (clone_root / str(target_user) / str(uuid.uuid4())).mkdir(parents=True)
    sibling_marker = clone_root / str(sibling_user) / "marker"
    sibling_marker.parent.mkdir(parents=True)
    sibling_marker.write_text("keep")
    legacy_marker = clone_root / "github" / "owner" / "repo" / "marker"
    legacy_marker.parent.mkdir(parents=True)
    legacy_marker.write_text("legacy")

    assert asyncio.run(repository_paths.delete_user_clone_storage(target_user)) is True

    assert not (clone_root / str(target_user)).exists()
    assert sibling_marker.read_text() == "keep"
    assert legacy_marker.read_text() == "legacy"
