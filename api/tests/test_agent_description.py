"""Draft descriptions use authenticated inference without executing Agent instructions."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from routers import agents
from schemas.agents import AgentDescriptionRequest
from services.agents import description


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def inference(monkeypatch):
    credentials = AsyncMock(return_value=object())
    build = lambda **kwargs: SimpleNamespace(**kwargs)
    generate = AsyncMock(return_value='[THINK]Private reasoning[!THINK]\nFinds reliable sources.\n')
    monkeypatch.setattr(description, "get_user_inference_credentials", credentials)
    monkeypatch.setattr(description, "build_inference_request", build)
    monkeypatch.setattr(description, "make_inference_request_non_streaming", generate)
    return credentials, generate


@pytest.mark.anyio
async def test_description_uses_selected_model_and_no_tools_or_graph_mutations(inference):
    payload = AgentDescriptionRequest(name="Researcher", instructions="Find sources.", model="test/model")
    result = await description.generate_description(None, "owner", payload, None, [{"id": "test/model"}])
    assert result.description == "Finds reliable sources."
    request = inference[1].call_args.args[0]
    assert request.model == "test/model"
    assert request.selected_tools == [] and request.stream is False
    assert request.is_title_generation is True
    assert not hasattr(request, "graph_id")
    assert request.messages[1]["role"] == "user" and "Find sources." in request.messages[1]["content"]
    assert request.config.max_tokens == 512


@pytest.mark.anyio
@pytest.mark.parametrize("instructions,model", [("   ", "test/model"), ("Find sources", "unknown/model")])
async def test_description_rejects_empty_instructions_and_unavailable_models(inference, instructions, model):
    with pytest.raises(HTTPException) as exc:
        await description.generate_description(None, "owner", AgentDescriptionRequest(instructions=instructions, model=model), None, [{"id": "test/model"}])
    assert exc.value.status_code == 422
    inference[0].assert_not_awaited()
    inference[1].assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("result", ["", "[THINK]Only reasoning[!THINK]", "x" * 2001, RuntimeError("secret")])
async def test_description_provider_failures_are_retryable_and_do_not_expose_details(inference, result):
    if isinstance(result, Exception):
        inference[1].side_effect = result
    else:
        inference[1].return_value = result
    with pytest.raises(HTTPException) as exc:
        await description.generate_description(None, "owner", AgentDescriptionRequest(instructions="Find sources", model="test/model"), None, [{"id": "test/model"}])
    assert exc.value.status_code == 502
    assert "Try again" in exc.value.detail and "secret" not in exc.value.detail


@pytest.mark.anyio
async def test_description_api_requires_authentication(monkeypatch):
    app = FastAPI()
    app.include_router(agents.router)
    async def deny():
        raise HTTPException(401, "Not authenticated")
    app.dependency_overrides[agents.agent_user_id] = deny
    generate = AsyncMock()
    monkeypatch.setattr(description, "generate_description", generate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post('/agents/generate-description', json={"model": "test/model", "instructions": "Find sources"})
    assert response.status_code == 401
    generate.assert_not_awaited()


@pytest.mark.anyio
async def test_authenticated_description_api_validates_payload_and_returns_description(monkeypatch):
    import uuid
    from schemas.agents import AgentDescriptionResponse
    app = FastAPI()
    app.include_router(agents.router)
    app.state.pg_engine, app.state.http_client = object(), object()
    owner = uuid.uuid4()
    app.dependency_overrides[agents.agent_user_id] = lambda: owner
    catalog = SimpleNamespace(data=[SimpleNamespace(model_dump=lambda: {"id": "test/model"})])
    monkeypatch.setattr(agents, "get_available_models_for_user", AsyncMock(return_value=catalog))
    generate = AsyncMock(return_value=AgentDescriptionResponse(description="Finds evidence."))
    monkeypatch.setattr(description, "generate_description", generate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post('/agents/generate-description', json={"model": "test/model", "instructions": ""})
        assert invalid.status_code == 422
        generate.assert_not_awaited()
        result = await client.post('/agents/generate-description', json={"model": "test/model", "instructions": "Find sources"})
    assert result.status_code == 200 and result.json() == {"description": "Finds evidence."}
    assert generate.call_args.args[1] == str(owner)
    assert generate.call_args.args[2].instructions == "Find sources"
