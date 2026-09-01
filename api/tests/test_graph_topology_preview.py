import asyncio
import datetime
import importlib.util
import sys
import uuid
from pathlib import Path
from types import TracebackType
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

from database.pg.graph_ops import graph_crud, graph_node_crud
from database.pg.models import Graph, Node
from schemas.topology_preview import TopologyPreviewV1
from services.graph_topology_preview import build_topology_preview

GRAPH_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
EMPTY_PREVIEW = {
    "version": 1,
    "width": 1000,
    "height": 600,
    "nodes": [],
    "edges": [],
}
EXPECTED_COLUMN_SQL = (
    'topology_preview JSONB DEFAULT \'{"version":1,"width":1000,"height":600,'
    '"nodes":[],"edges":[]}\'::jsonb NOT NULL'
)


def _graph(**values: object) -> Graph:
    return Graph(
        id=GRAPH_ID,
        user_id=USER_ID,
        name="Graph",
        **values,
    )


def _node() -> Node:
    return Node(
        id="node",
        graph_id=GRAPH_ID,
        type="prompt",
        position_x=10,
        position_y=20,
        width="120",
        height="80",
        data={"prompt": "private", "reply": "secret"},
    )


def test_graph_model_uses_fresh_matching_python_and_server_defaults() -> None:
    first = Graph(name="First")
    second = Graph(name="Second")

    assert first.topology_preview == EMPTY_PREVIEW
    assert second.topology_preview == EMPTY_PREVIEW
    first.topology_preview["nodes"].append(  # type: ignore[union-attr]
        {"x": 0, "y": 0, "width": 1, "height": 1}
    )
    assert second.topology_preview == EMPTY_PREVIEW

    column = Graph.__table__.c.topology_preview  # type: ignore[attr-defined]
    assert column.nullable is False
    assert str(CreateColumn(column).compile(dialect=postgresql.dialect())) == EXPECTED_COLUMN_SQL


def test_migration_renders_empty_v1_default_without_bind_parameters() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "ae52881f1633_add_graph_topology_preview.py"
    )
    spec = importlib.util.spec_from_file_location(
        "graph_topology_preview_migration", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    with patch.object(migration.op, "add_column") as add_column:
        migration.upgrade()

    add_column.assert_called_once()
    table_name, column = add_column.call_args.args
    assert table_name == "graphs"
    assert str(CreateColumn(column).compile(dialect=postgresql.dialect())) == EXPECTED_COLUMN_SQL
    assert migration.revision == "ae52881f1633"
    assert migration.down_revision == "4e7a9c2b6d10"


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class _ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def scalars(self) -> "_ScalarsResult":
        return self

    def all(self) -> list[object]:
        return self.values


class _Transaction:
    def __init__(self) -> None:
        self.rolled_back = False

    async def __aenter__(self) -> "_Transaction":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.rolled_back = exc_type is not None
        return False


class _NoAutoflush:
    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


class _UpdateSession:
    def __init__(self, graph: Graph) -> None:
        self.transaction = _Transaction()
        self.added: list[object] = []
        self.results = iter(
            [
                _ScalarResult(graph),
                _ScalarsResult([]),
                _ScalarsResult([]),
            ]
        )
        self.no_autoflush = _NoAutoflush()

    async def __aenter__(self) -> "_UpdateSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def begin(self) -> _Transaction:
        return self.transaction

    async def exec(self, statement: object) -> object:
        return next(self.results)

    async def flush(self) -> None:
        return None

    def add(self, value: object) -> None:
        self.added.append(value)


def test_full_save_replaces_request_preview_and_rolls_assignment_back_on_failure() -> None:
    persisted = _graph(topology_preview={"untrusted": "old"})
    request_graph = _graph(
        topology_preview={
            "version": 1,
            "width": 1000,
            "height": 600,
            "nodes": [{"x": 1, "y": 1, "width": 1, "height": 1}],
            "edges": [],
        }
    )
    node = _node()
    session = _UpdateSession(persisted)

    with (
        patch.object(graph_node_crud, "AsyncSession", return_value=session),
        patch.object(
            graph_node_crud,
            "update_neo4j_graph",
            new=AsyncMock(side_effect=RuntimeError("neo4j failed")),
        ),
        pytest.raises(RuntimeError, match="neo4j failed"),
    ):
        asyncio.run(
            graph_node_crud.update_graph_with_nodes_and_edges(
                object(),  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
                str(GRAPH_ID),
                str(USER_ID),
                request_graph,
                [node],
                [],
                10,
            )
        )

    expected = build_topology_preview([node], []).model_dump(mode="json")
    assert persisted.topology_preview == expected
    assert persisted.topology_preview != request_graph.topology_preview
    assert session.transaction.rolled_back is True
    assert "private" not in repr(persisted.topology_preview)
    assert "secret" not in repr(persisted.topology_preview)


def test_preview_generation_failure_happens_before_database_access() -> None:
    with (
        patch.object(
            graph_node_crud,
            "build_topology_preview",
            side_effect=ValueError("invalid generated preview"),
        ),
        patch.object(
            graph_node_crud,
            "AsyncSession",
            side_effect=AssertionError("database must not be accessed"),
        ),
        pytest.raises(ValueError, match="invalid generated preview"),
    ):
        asyncio.run(
            graph_node_crud.update_graph_with_nodes_and_edges(
                object(),  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
                str(GRAPH_ID),
                str(USER_ID),
                _graph(),
                [_node()],
                [],
                10,
            )
        )


class _SummaryResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self.rows


class _SummarySession:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def __aenter__(self) -> "_SummarySession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    async def exec(self, statement: object) -> _SummaryResult:
        self.statement = statement
        return _SummaryResult(self.rows)


def _summary_row(graph_id: uuid.UUID, preview: object) -> tuple[object, ...]:
    return (
        graph_id,
        "Summary",
        None,
        None,
        False,
        True,
        datetime.datetime(2026, 8, 31, tzinfo=datetime.timezone.utc),
        preview,
        7,
    )


def test_summary_query_returns_required_validated_preview_and_preserves_pagination() -> None:
    preview = build_topology_preview([_node()], []).model_dump(mode="json")
    rows = [_summary_row(GRAPH_ID, preview), _summary_row(uuid.uuid4(), EMPTY_PREVIEW)]
    session = _SummarySession(rows)

    with patch.object(graph_crud, "AsyncSession", return_value=session):
        page = asyncio.run(graph_crud.get_all_graphs(object(), str(USER_ID), offset=3, limit=1))  # type: ignore[arg-type]

    assert page.has_more is True
    assert page.next_offset == 4
    assert len(page.items) == 1
    assert page.items[0].node_count == 7
    assert page.items[0].topology_preview == TopologyPreviewV1.model_validate(preview)
    assert "graphs.topology_preview" in str(session.statement)


def test_summary_rejects_invalid_persisted_preview() -> None:
    invalid_preview = {**EMPTY_PREVIEW, "version": 2}
    session = _SummarySession([_summary_row(GRAPH_ID, invalid_preview)])

    with (
        patch.object(graph_crud, "AsyncSession", return_value=session),
        pytest.raises(ValidationError),
    ):
        asyncio.run(graph_crud.get_all_graphs(object(), str(USER_ID)))  # type: ignore[arg-type]
