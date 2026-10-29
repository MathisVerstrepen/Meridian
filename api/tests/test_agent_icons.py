"""Custom Agent icons remain bounded, inert geometry through every profile write."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from schemas.agents import AgentIconRequest, AgentWrite
from services.agents import icon_generation
from utils.svg_icon import normalize_svg_icon

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="8"/><path d="M8 12l3 3 5-6"/></svg>'


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_svg_normalization_preserves_geometry_and_uses_accent_color():
    normalized = normalize_svg_icon(SVG.replace('stroke="currentColor"', 'stroke="#000000"'))
    assert 'stroke="currentColor"' in normalized
    assert 'width="24"' in normalized and 'height="24"' in normalized
    assert normalize_svg_icon(normalized) == normalized
    payload = AgentWrite(handle="research", name="Researcher", model_settings={"model": "test/model"}, iconSvg=SVG)
    assert payload.iconSvg == normalize_svg_icon(SVG)
    assert AgentWrite.model_validate(payload.model_dump()).iconSvg == payload.iconSvg


@pytest.mark.parametrize("content", [
    '<script>alert(1)</script>', '<foreignObject><div>Hi</div></foreignObject>',
    '<image href="https://example.com/image.svg"/>', '<use href="#loop"/>',
    '<animate attributeName="x" dur="1s" repeatCount="indefinite"/>',
    '<filter id="f"><feTurbulence/></filter>', '<text>hello</text>', '<svg/>',
    '<circle cx="12" cy="12" r="8" onclick="alert(1)"/>',
    '<path d="M1 1L2 2" fill="url(https://example.com/icon)"/>',
    '<path d="M1 1L2 2" style="fill:red"/>',
    '<path d="M1 1L2 2" transform="url(https://example.com)"/>',
    '<circle cx="1e99999" r="8"/>', '<circle r="-8"/>', '<circle r="8" opacity="2"/>',
    '<g xmlns="https://example.com"><path d="M1 1L2 2"/></g>',
])
def test_unsafe_svg_rejected_on_profile_write(content):
    svg = f'<svg viewBox="0 0 24 24">{content}</svg>'
    with pytest.raises(ValidationError):
        AgentWrite(handle="research", name="Researcher", model_settings={"model": "test/model"}, iconSvg=svg)


@pytest.mark.parametrize("svg", [
    '<!DOCTYPE svg [<!ENTITY x "expanded">]><svg viewBox="0 0 24 24"><title>&x;</title><path d="M1 1L2 2"/></svg>',
    '<\x00!\x00D\x00O\x00C\x00T\x00Y\x00P\x00E\x00 svg>',
    '<?xml-stylesheet href="https://example.com"?><svg/>',
    '<svg viewBox="0 0 24 24">' + '<g>' * 9 + '<circle r="1"/>' + '</g>' * 9 + '</svg>',
    '<svg viewBox="0 0 24 24">' + '<circle r="1"/>' * 129 + '</svg>',
    '<svg viewBox="0 0 24 24">' + ' ' * 24000 + '</svg>',
    '<svg viewBox="0 0 0 24"><path d="M1 1L2 2"/></svg>',
    '<svg><path d="M1 1L2 2"/></svg>', '<html/>', '<svg viewBox="0 0 24 24"/>',
])
def test_svg_resource_limits_and_declarations_rejected(svg):
    with pytest.raises(ValueError):
        normalize_svg_icon(svg)


@pytest.mark.anyio
async def test_icon_generation_uses_role_context_and_returns_validated_svg(monkeypatch):
    credentials = AsyncMock(return_value=object())
    generate = AsyncMock(return_value='[THINK]Designing[!THINK]\n```svg\n' + SVG + '\n```')
    monkeypatch.setattr(icon_generation, "get_user_inference_credentials", credentials)
    monkeypatch.setattr(icon_generation, "build_inference_request", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(icon_generation, "make_inference_request_non_streaming", generate)
    data = AgentIconRequest(name="Researcher", description="Find evidence", instructions="Cite sources", model="test/model", tools=["web_search"], tags=["research"])
    result = await icon_generation.generate_icon(None, "owner", data, None, [{"id": "test/model"}])
    assert result.iconSvg == normalize_svg_icon(SVG)
    request = generate.call_args.args[0]
    assert request.selected_tools == [] and not request.stream and not request.is_title_generation
    assert request.model == "test/model"
    assert request.config.max_tokens == 16384 and not request.config.exclude_reasoning
    assert request.config.reasoning_effort == "low"
    assert "Cite sources" in request.messages[1]["content"] and "Find evidence" in request.messages[1]["content"]


@pytest.mark.anyio
@pytest.mark.parametrize("response", ['', '<svg viewBox="0 0 24 24"><script>alert(1)</script></svg>', RuntimeError('secret')])
async def test_generation_failure_exposes_retryable_error_not_provider_details(monkeypatch, response):
    monkeypatch.setattr(icon_generation, "get_user_inference_credentials", AsyncMock(return_value=object()))
    monkeypatch.setattr(icon_generation, "build_inference_request", lambda **kw: SimpleNamespace(**kw))
    generate = AsyncMock(side_effect=response) if isinstance(response, Exception) else AsyncMock(return_value=response)
    monkeypatch.setattr(icon_generation, "make_inference_request_non_streaming", generate)
    with pytest.raises(HTTPException) as error:
        await icon_generation.generate_icon(None, "owner", AgentIconRequest(name="Researcher", model="test/model"), None, [{"id": "test/model"}])
    assert error.value.status_code == 502 and 'Try again' in error.value.detail
    assert 'secret' not in error.value.detail


@pytest.mark.anyio
async def test_empty_context_and_unavailable_model_fail_before_inference(monkeypatch):
    credentials = AsyncMock()
    monkeypatch.setattr(icon_generation, "get_user_inference_credentials", credentials)
    for data in [AgentIconRequest(model="test/model"), AgentIconRequest(name="Researcher", model="unknown/model")]:
        with pytest.raises(HTTPException) as error:
            await icon_generation.generate_icon(None, "owner", data, None, [{"id": "test/model"}])
        assert error.value.status_code == 422
    credentials.assert_not_awaited()


@pytest.mark.anyio
async def test_icon_generation_endpoint_requires_authentication(monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from routers import agents
    app = FastAPI()
    app.include_router(agents.router)
    async def deny():
        raise HTTPException(401, "Not authenticated")
    app.dependency_overrides[agents.agent_user_id] = deny
    generate = AsyncMock()
    monkeypatch.setattr(icon_generation, "generate_icon", generate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post('/agents/generate-icon', json={"model": "test/model", "name": "Researcher"})
    assert response.status_code == 401
    generate.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("provider_model", ["opencode-go/deepseek-v4.1-flash", "test/model"])
async def test_icon_endpoint_returns_svg_with_thinking_enabled_adapter(monkeypatch, provider_model):
    import json
    import uuid
    import httpx
    from fastapi import FastAPI
    from models.inference import InferenceCredentials
    from routers import agents

    calls = []
    def provider(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if provider_model.startswith("opencode-go/"):
            assert payload["model"] == "deepseek-v4.1-flash"
            assert payload["thinking"] == {"type": "enabled"}
            assert payload["reasoning_effort"] == "low"
        else:
            assert payload["reasoning"]["enabled"] is True
            assert payload["reasoning"]["exclude"] is False
            assert payload["reasoning"]["effort"] == "low"
        assert payload["max_tokens"] == 16384
        assert "tools" not in payload
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": SVG}}]})
    model = {"id": provider_model, "architecture": {"output_modalities": ["text"]}}
    catalog = SimpleNamespace(data=[SimpleNamespace(model_dump=lambda: model)])
    monkeypatch.setattr(agents, "get_available_models_for_user", AsyncMock(return_value=catalog))
    monkeypatch.setattr(icon_generation, "get_user_inference_credentials", AsyncMock(return_value=InferenceCredentials(opencode_go_api_key="test-key", openrouter_api_key="test-key")))
    app = FastAPI()
    app.include_router(agents.router)
    app.state.pg_engine = None
    owner = uuid.uuid4()
    app.dependency_overrides[agents.agent_user_id] = lambda: owner
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as upstream:
        app.state.http_client = upstream
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post('/agents/generate-icon', json={"name": "Misc", "instructions": "Follow the given task", "model": model["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["iconSvg"] == normalize_svg_icon(SVG)
    assert len(calls) == 1


def test_common_generated_svg_scaffolding_and_safe_styles_are_normalized():
    from services.agents.icon_output import normalize_icon_output
    generated = '''Here is your icon:
```SVG
<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" aria-label="Research" version="1.1">
<!-- Search metaphor -->
<g id="search" class="outline" style="fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round;">
<circle cx="10" cy="10" r="6"/><path d="M15 15L20 20" stroke-miterlimit="10"/>
</g></svg>
```
'''
    result = normalize_icon_output(generated)
    assert result.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'style=' not in result and 'aria-label' not in result and 'class=' not in result
    assert '<!--' not in result and '<?xml' not in result
    assert 'stroke="currentColor"' in result and 'stroke-width="2"' in result
    assert normalize_svg_icon(result) == result


@pytest.mark.parametrize("style", [
    'fill:url(https://example.com/image)', 'filter:url(https://example.com/filter)',
    'stroke:expression(alert(1))', 'background:url(https://example.com/image)',
    'animation:test 1s infinite',
])
def test_style_normalization_never_accepts_active_or_external_content(style):
    with pytest.raises(ValueError):
        normalize_svg_icon(f'<svg viewBox="0 0 24 24"><circle r="8" style="{style}"/></svg>')


@pytest.mark.anyio
async def test_invalid_generation_gets_one_corrective_attempt_with_same_model_and_no_tools(monkeypatch):
    monkeypatch.setattr(icon_generation, "get_user_inference_credentials", AsyncMock(return_value=object()))
    monkeypatch.setattr(icon_generation, "build_inference_request", lambda **kw: SimpleNamespace(**kw))
    responses = iter(['<svg viewBox="0 0 24 24"><path d="M1 1"', 'SVG result:\n```svg\n' + SVG + '\n```'])
    requests = []
    async def provider(request, engine):
        requests.append({"model": request.model, "tools": list(request.selected_tools), "messages": list(request.messages)})
        return next(responses)
    monkeypatch.setattr(icon_generation, "make_inference_request_non_streaming", provider)
    result = await icon_generation.generate_icon(None, "owner", AgentIconRequest(name="Misc", model="test/model"), None, [{"id": "test/model"}])
    assert result.iconSvg == normalize_svg_icon(SVG)
    assert len(requests) == 2 and all(request["model"] == 'test/model' and request["tools"] == [] for request in requests)
    assert len(requests[1]["messages"]) == len(requests[0]["messages"]) + 1
    assert 'replacement SVG' in requests[1]["messages"][-1]["content"]


@pytest.mark.anyio
async def test_invalid_generation_stops_after_two_attempts(monkeypatch):
    monkeypatch.setattr(icon_generation, "get_user_inference_credentials", AsyncMock(return_value=object()))
    monkeypatch.setattr(icon_generation, "build_inference_request", lambda **kw: SimpleNamespace(**kw))
    provider = AsyncMock(return_value='Not SVG')
    monkeypatch.setattr(icon_generation, "make_inference_request_non_streaming", provider)
    with pytest.raises(HTTPException) as failure:
        await icon_generation.generate_icon(None, "owner", AgentIconRequest(name="Misc", model="test/model"), None, [{"id": "test/model"}])
    assert failure.value.status_code == 502
    assert failure.value.headers == {"X-Agent-Icon-Error": "svg_validation:ValueError"}
    assert provider.await_count == 2
