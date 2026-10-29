"""Main-model automatic tool selection retains server-side execution policy."""

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.chatDTO import GenerateRequest
from models.message import ToolEnum
from schemas.agents import AgentNodeConfig
from services import stream
from services.agents import main_tools


@pytest.fixture
def anyio_backend():
    return "asyncio"


def execution(auto=True):
    team_id = uuid.uuid4()
    return SimpleNamespace(
        node_config=AgentNodeConfig(model="test/server", teamId=team_id,
                                   autoSelectTools=auto, selectedTools=[ToolEnum.EXECUTE_CODE]),
        node_data={"model": "test/server", "teamId": str(team_id), "autoSelectTools": auto},
        request=GenerateRequest(graph_id=str(uuid.uuid4()), node_id="node", model="client/model",
                                stream_type="agent"),
        engine=object(), neo4j_driver=object(), user_id=uuid.uuid4(), http_client=object(),
        config=object(), credentials=object(), available_models=[], state={})


@pytest.mark.anyio
async def test_auto_tools_use_persisted_model_and_keep_selection_for_resume(monkeypatch):
    run = execution()
    selector = AsyncMock(return_value=[ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION])
    monkeypatch.setattr(stream, "_resolve_auto_selected_tools", selector)
    monkeypatch.setattr(main_tools, "get_user_settings", AsyncMock(return_value=object()))
    candidates = [ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION, ToolEnum.ASK_USER]
    monkeypatch.setattr(stream, "_get_auto_tool_candidates", lambda *args: candidates)
    assert await main_tools.resolve_main_tools(run) == candidates[:2]
    assert selector.call_args.kwargs["request_data"].model == "test/server"
    assert selector.call_args.kwargs["node"][0].data is run.node_data
    assert run.state["auto_selected_tools"] == ["web_search", "link_extraction"]
    # Current capabilities/settings restrict the saved policy on subsequent rounds/resume.
    candidates[:] = [ToolEnum.LINK_EXTRACTION]
    assert await main_tools.resolve_main_tools(run) == [ToolEnum.LINK_EXTRACTION]
    assert selector.await_count == 1
    # Turning auto off uses the current manual policy, not its prior automatic selection.
    run.node_config.autoSelectTools = False
    assert await main_tools.resolve_main_tools(run) == [ToolEnum.EXECUTE_CODE]


@pytest.mark.anyio
async def test_manual_selection_never_runs_selector_or_reads_settings(monkeypatch):
    monkeypatch.setattr(stream, "_resolve_auto_selected_tools", AsyncMock(side_effect=AssertionError))
    monkeypatch.setattr(main_tools, "get_user_settings", AsyncMock(side_effect=AssertionError))
    assert await main_tools.resolve_main_tools(execution(auto=False)) == [ToolEnum.EXECUTE_CODE]


@pytest.mark.anyio
async def test_empty_automatic_selection_does_not_inherit_manual_tools(monkeypatch):
    monkeypatch.setattr(stream, "_resolve_auto_selected_tools", AsyncMock(return_value=[]))
    monkeypatch.setattr(main_tools, "get_user_settings", AsyncMock(return_value=object()))
    monkeypatch.setattr(stream, "_get_auto_tool_candidates", lambda *args: list(ToolEnum))
    assert await main_tools.resolve_main_tools(execution()) == []
