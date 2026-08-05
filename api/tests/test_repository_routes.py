import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

_ORIGINAL_WORKING_DIRECTORY = Path.cwd()
os.chdir(Path(__file__).resolve().parents[1] / "app")
try:
    from routers import repository  # noqa: E402
finally:
    os.chdir(_ORIGINAL_WORKING_DIRECTORY)


@pytest.mark.parametrize(
    "method,path,limit,service_name,service_response",
    [
        ("get", "/repositories", 30, "list_available_repositories_service", []),
        (
            "post",
            "/repositories/clone",
            2,
            "clone_repository",
            {"message": "Repository cloned successfully.", "path": "scoped"},
        ),
        (
            "get",
            "/repositories/Z2l0aHVi/owner/repo/branches",
            10,
            "get_repository_branches",
            [],
        ),
        (
            "get",
            "/repositories/Z2l0aHVi/owner/repo/tree?branch=main",
            30,
            "get_repository_tree",
            {},
        ),
        (
            "get",
            "/repositories/Z2l0aHVi/owner/repo/content/README.md?branch=main",
            60,
            "get_repository_file_content",
            {"content": ""},
        ),
        (
            "post",
            "/repositories/Z2l0aHVi/owner/repo/pull?branch=main",
            5,
            "pull_repository_service",
            {"message": "Successfully pulled branch 'main'."},
        ),
        (
            "get",
            "/repositories/Z2l0aHVi/owner/repo/issues",
            20,
            "get_repository_issues",
            [],
        ),
        (
            "get",
            "/repositories/Z2l0aHVi/owner/repo/commit-state?branch=main",
            20,
            "get_repository_commit_state_service",
            {
                "latest_local": {
                    "hash": "abc",
                    "author": "author",
                    "date": datetime.now(timezone.utc),
                },
                "latest_online": {
                    "hash": "abc",
                    "author": "author",
                    "date": datetime.now(timezone.utc),
                },
                "is_up_to_date": True,
            },
        ),
    ],
)
def test_repository_route_limit_threshold_plus_one(
    monkeypatch, method, path, limit, service_name, service_response
):
    async def response(*_args, **_kwargs):
        return service_response

    monkeypatch.setattr(repository, service_name, response)
    memory_storage = MemoryStorage()
    monkeypatch.setattr(repository.limiter, "_storage", memory_storage)
    monkeypatch.setattr(
        repository.limiter,
        "_limiter",
        FixedWindowRateLimiter(memory_storage),
    )
    repository.limiter.reset()
    app = FastAPI()
    app.state.limiter = repository.limiter
    app.state.pg_engine = "engine"
    app.state.git_http_client = "http-client"
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(repository.router)
    app.dependency_overrides[repository.get_current_user_id] = lambda: "user"

    payload = {
        "provider": "github",
        "full_name": "owner/repo",
        "clone_url": "https://example/repo",
        "clone_method": "https",
    }
    request_kwargs = {"json": payload} if method == "post" else {}
    with TestClient(app) as client:
        for _ in range(limit):
            response_message = getattr(client, method)(path, **request_kwargs)
            assert response_message.status_code < 400
        limited_response = getattr(client, method)(path, **request_kwargs)

    assert limited_response.status_code == 429
