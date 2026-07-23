import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

_ORIGINAL_WORKING_DIRECTORY = Path.cwd()
os.chdir(Path(__file__).resolve().parents[1] / "app")
try:
    from routers import users  # noqa: E402
finally:
    os.chdir(_ORIGINAL_WORKING_DIRECTORY)


def test_account_cleanup_attempts_file_and_clone_storage(monkeypatch):
    calls = []

    async def delete_row(*_args):
        calls.append("database")

    async def delete_files(*_args):
        calls.append("files")
        return False

    async def delete_clones(*_args):
        calls.append("clones")
        return True

    monkeypatch.setattr(users, "delete_user_by_id", delete_row)
    monkeypatch.setattr(users, "delete_user_storage", delete_files)
    monkeypatch.setattr(users, "delete_user_clone_storage", delete_clones)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine="engine")))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(users._delete_user_account_data(request, str(uuid.uuid4())))

    assert exc_info.value.status_code == 500
    assert calls == ["database", "files", "clones"]
