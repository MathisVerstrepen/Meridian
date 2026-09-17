import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.chat_ops import tool_call_crud
from services import tool_history

USER = str(uuid.UUID(int=100))
GRAPH = str(uuid.UUID(int=200))


@pytest.fixture
def anyio_backend():
    return "asyncio"


def row(seed=1, name="web_search", **values):
    return SimpleNamespace(
        **{
            "id": uuid.UUID(int=seed),
            "tool_name": name,
            "arguments": {"query": "hello"},
            "model_context_payload": "MODEL_FACT",
            "result": {"private": "RAW_PRIVATE"},
            **values,
        }
    )


def tag(seed=1, name="search_query"):
    return f'<{name} id="{uuid.UUID(int=seed)}">card</{name}>'


@pytest.mark.parametrize(
    "source,expected",
    [
        ("before<tool_call_context>RAW</tool_call_context>after", "beforeafter"),
        (
            "a<tool_call_context id='x'>RAW</tool_call_context>b<tool_call_context>RAW</tool_call_context>c",
            "abc",
        ),
        ("a<tool_call_context\n id='x'>unfinished", "a"),
        ("a<tool_call_context/ unfinished", "a"),
        (
            "a<tool_call_contextual>normal</tool_call_contextual>b",
            "a<tool_call_contextual>normal</tool_call_contextual>b",
        ),
        ("<tool_call_context", "<tool_call_context"),
        ("&lt;tool_call_context&gt;example", "&lt;tool_call_context&gt;example"),
        ('Arguments: {"x":1}\nResult: normal', 'Arguments: {"x":1}\nResult: normal'),
    ],
)
def test_reserved_cleanup(source, expected):
    assert tool_history.clean_legacy_tool_context(source) == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "runtime,summary",
    [
        ("web_search", "search_query"),
        ("fetch_page_content", "fetch_url"),
        ("generate_image", "generating_image"),
        ("generate_video", "generating_video"),
        ("execute_code", "executing_code"),
        ("visualise", "visualising"),
        ("ask_user", "asking_user"),
    ],
)
async def test_scoped_pair_only_uses_persisted_model_payload(monkeypatch, runtime, summary):
    query = AsyncMock(return_value=[row(name=runtime)])
    monkeypatch.setattr(tool_history, "get_completed_tool_calls_for_history", query)
    reply = f"{tag(name=summary)}{tag(name=summary)}<tool_call_context>{tag(2)}</tool_call_context>"
    messages = await tool_history.build_tool_history(
        reply, pg_engine="engine", user_id=USER, graph_id=GRAPH, node_id="node", model_id="entry"
    )
    query.assert_awaited_once_with(
        "engine",
        user_id=USER,
        graph_id=GRAPH,
        node_id="node",
        model_id="entry",
        tool_call_ids=[str(uuid.UUID(int=1))],
    )
    assert [message.role.value for message in messages] == ["assistant", "tool"]
    call = messages[0].tool_calls[0]
    assert call.id == messages[1].tool_call_id == f"hist_{uuid.UUID(int=1).hex}"
    assert call.function.name == messages[1].name == runtime
    assert json.loads(call.function.arguments) == {"query": "hello"}
    assert messages[0].content == []
    assert messages[1].content[0].text == "MODEL_FACT"
    assert "RAW_PRIVATE" not in str(messages)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "reply",
    [
        "answer",
        tag(name="inspect_image"),
        '<search_query id="bad">x</search_query>',
        f"<tool_call_context>{tag()}</tool_call_context>",
    ],
)
async def test_no_eligible_references_means_no_query(monkeypatch, reply):
    query = AsyncMock()
    monkeypatch.setattr(tool_history, "get_completed_tool_calls_for_history", query)
    assert (
        await tool_history.build_tool_history(
            reply, pg_engine=None, user_id=USER, graph_id=GRAPH, node_id="n"
        )
        == []
    )
    query.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid",
    [
        row(name="execute_code"),
        row(arguments=[]),
        row(arguments={"x": float("nan")}),
        row(arguments={"x": object()}),
        row(model_context_payload=" "),
        row(model_context_payload=None),
        row(model_context_payload={"raw": "bad"}),
        row(seed=2),
    ],
)
async def test_invalid_or_mismatched_rows_omit_whole_pair(monkeypatch, invalid, caplog):
    monkeypatch.setattr(
        tool_history, "get_completed_tool_calls_for_history", AsyncMock(return_value=[invalid])
    )
    assert (
        await tool_history.build_tool_history(
            tag(), pg_engine=None, user_id=USER, graph_id=GRAPH, node_id="n"
        )
        == []
    )
    assert "RAW_PRIVATE" not in caplog.text


@pytest.mark.anyio
async def test_missing_rows_and_stable_database_order(monkeypatch):
    query = AsyncMock(return_value=[])
    monkeypatch.setattr(tool_history, "get_completed_tool_calls_for_history", query)
    kwargs = dict(pg_engine=None, user_id=USER, graph_id=GRAPH, node_id="n")
    assert await tool_history.build_tool_history(tag(), **kwargs) == []
    query.return_value = [
        row(1, tool_call_id=None),
        row(2, tool_call_id="repeated"),
        row(3, tool_call_id="repeated"),
    ]
    messages = await tool_history.build_tool_history(tag(3) + tag(1) + tag(2), **kwargs)
    assert [message.tool_call_id for message in messages[1::2]] == [
        f"hist_{uuid.UUID(int=i).hex}" for i in (1, 2, 3)
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("model_id", [None, "entry-not-provider-slug"])
async def test_query_has_all_isolation_status_and_order_predicates(monkeypatch, model_id):
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.exec.return_value = result
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    monkeypatch.setattr(tool_call_crud, "AsyncSession", factory)
    await tool_call_crud.get_completed_tool_calls_for_history(
        None,
        user_id=USER,
        graph_id=GRAPH,
        node_id="node-scope",
        model_id=model_id,
        tool_call_ids=[str(uuid.UUID(int=1))],
    )
    statement = session.exec.call_args.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    sql = str(compiled)
    for expected in (
        f"tool_calls.user_id = '{USER}'",
        f"tool_calls.graph_id = '{GRAPH}'",
        "tool_calls.node_id = 'node-scope'",
        f"tool_calls.id IN ('{uuid.UUID(int=1)}')",
        "tool_calls.status IN ('success', 'error')",
        "ORDER BY tool_calls.created_at ASC, tool_calls.id ASC",
    ):
        assert expected in sql
    assert (
        "tool_calls.model_id IS NULL" if model_id is None else f"tool_calls.model_id = '{model_id}'"
    ) in sql
    assert "pending" not in sql
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.anyio
async def test_empty_reference_query_never_opens_session(monkeypatch):
    factory = MagicMock(side_effect=AssertionError("unexpected database access"))
    monkeypatch.setattr(tool_call_crud, "AsyncSession", factory)
    assert (
        await tool_call_crud.get_completed_tool_calls_for_history(
            None, user_id=USER, graph_id=GRAPH, node_id="n", tool_call_ids=[]
        )
        == []
    )
