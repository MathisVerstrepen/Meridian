import asyncio
import importlib
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))
importlib.import_module("services.graph_service")

from services.opencode_go import OpenCodeGoReqChat, validate_opencode_go_api_key  # noqa: E402


def _request(
    *,
    model: str = "opencode-go/kimi-k3",
    user_id: str = "user-1",
    graph_id: str | None = "graph-1",
    stream: bool = True,
    is_title_generation: bool = False,
) -> OpenCodeGoReqChat:
    return OpenCodeGoReqChat(
        api_key="test-key",
        model=model,
        messages=[{"role": "user", "content": "Hello"}],
        config=SimpleNamespace(),
        user_id=user_id,
        graph_id=graph_id,
        pg_engine=MagicMock(),
        http_client=MagicMock(),
        stream=stream,
        is_title_generation=is_title_generation,
    )


@pytest.mark.parametrize(
    "model", ["opencode-go/kimi-k3", "opencode-go/qwen3.7-plus", "opencode-go/grok-4.5"]
)
@pytest.mark.parametrize("stream", [True, False])
def test_conversation_session_survives_new_requests_and_protocol_changes(
    model: str, stream: bool
) -> None:
    first = _request()
    following = _request(model=model, stream=stream)
    title = _request(model=model, stream=False, is_title_generation=True)

    session_id = first.headers["x-opencode-session"]
    assert str(uuid.UUID(session_id)) == session_id
    assert following.headers["x-opencode-session"] == session_id
    assert title.headers["x-opencode-session"] == session_id
    assert following.headers["User-Agent"] == "Meridian/1.0"
    if following.uses_anthropic_protocol:
        assert following.headers["x-api-key"] == "test-key"
        assert following.headers["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in following.headers
    else:
        assert following.headers["Authorization"] == "Bearer test-key"
        assert "x-api-key" not in following.headers


def test_sessions_are_isolated_by_user_and_conversation() -> None:
    sessions = {
        _request().headers["x-opencode-session"],
        _request(user_id="user-2").headers["x-opencode-session"],
        _request(graph_id="graph-2").headers["x-opencode-session"],
    }

    assert len(sessions) == 3
    assert all("user-" not in session and "graph-" not in session for session in sessions)


def test_requests_without_a_graph_keep_a_local_session() -> None:
    first = _request(graph_id=None)
    second = _request(graph_id=None)
    first_headers = first.headers

    assert first.headers == first_headers
    assert first.headers["x-opencode-session"] != second.headers["x-opencode-session"]


@pytest.mark.parametrize("shared_client", [True, False])
def test_api_key_validation_sends_session_and_client_identity(shared_client: bool) -> None:
    sessions: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["User-Agent"] == "Meridian/1.0"
        session_id = request.headers["x-opencode-session"]
        assert str(uuid.UUID(session_id)) == session_id
        sessions.append(session_id)
        return httpx.Response(200, json={"choices": []})

    async def run() -> None:
        if shared_client:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await validate_opencode_go_api_key("test-key", http_client=client)
                await validate_opencode_go_api_key("test-key", http_client=client)
        else:
            for _ in range(2):
                client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
                with patch("services.opencode_go.httpx.AsyncClient", return_value=client):
                    await validate_opencode_go_api_key("test-key")

    asyncio.run(run())
    assert len(sessions) == 2
    assert sessions[0] != sessions[1]


def test_api_key_validation_still_rejects_invalid_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-opencode-session"]
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError, match=r"status 401.*Invalid API key"):
                await validate_opencode_go_api_key("invalid-key", http_client=client)

    asyncio.run(run())
