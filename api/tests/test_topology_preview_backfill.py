import asyncio
import datetime
import sys
import uuid
from pathlib import Path
from types import TracebackType
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy.dialects import postgresql

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

import main
from database.pg.models import Edge, Graph, Node
from schemas.topology_preview import empty_topology_preview_v2
from services import topology_preview_backfill as backfill

GRAPH_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
USER_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


class _ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def scalars(self) -> "_ScalarsResult":
        return self

    def all(self) -> list[object]:
        return self.values


class _Transaction:
    async def __aenter__(self) -> "_Transaction":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False


class _BackfillSession:
    def __init__(self, results: list[object]) -> None:
        self.results = iter(results)
        self.statements: list[object] = []

    async def __aenter__(self) -> "_BackfillSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def begin(self) -> _Transaction:
        return _Transaction()

    async def exec(self, statement: object) -> object:
        self.statements.append(statement)
        return next(self.results)


def _graph(graph_id: uuid.UUID = GRAPH_ID) -> Graph:
    return Graph(
        id=graph_id,
        user_id=USER_ID,
        name="Historical graph",
        updated_at=datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc),
    )


def _node(node_id: str = "node", *, position_x: float = 10) -> Node:
    return Node(
        id=node_id,
        graph_id=GRAPH_ID,
        type="prompt",
        position_x=position_x,
        position_y=20,
        width="120px",
        height="80px",
    )


def test_candidate_query_uses_exact_empty_v2_filter_and_waits_for_graph_locks() -> None:
    statement = backfill._candidate_statement(
        batch_size=7,
        deferred_graph_ids=frozenset(),
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "graphs.topology_preview = %(topology_preview_1)s::JSONB" in sql
    assert compiled.params["topology_preview_1"] == empty_topology_preview_v2()
    assert "EXISTS (SELECT nodes.id" in sql
    assert "nodes.graph_id = graphs.id" in sql
    assert compiled.params["param_1"] == 7
    assert "ORDER BY graphs.id" in sql
    assert "graphs.id >" not in sql
    assert "FOR UPDATE OF graphs" in sql
    assert "SKIP LOCKED" not in sql


def test_candidate_query_defers_only_generated_empty_graphs_without_cursor() -> None:
    statement = backfill._candidate_statement(
        batch_size=7,
        deferred_graph_ids=frozenset({GRAPH_ID}),
    )
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "graphs.id NOT IN" in sql
    assert compiled.params["id_1"] == [GRAPH_ID]
    assert "graphs.id >" not in sql
    assert "SKIP LOCKED" not in sql


def test_batch_generates_preview_from_postgres_geometry_without_changing_recency() -> None:
    graph = _graph()
    original_updated_at = graph.updated_at
    source = _node("source")
    target = _node("target", position_x=300)
    edge = Edge(
        id="edge",
        graph_id=GRAPH_ID,
        source_node_id="source",
        target_node_id="target",
    )
    session = _BackfillSession(
        [
            _ScalarsResult([graph]),
            _ScalarsResult([source, target]),
            _ScalarsResult([edge]),
            object(),
        ]
    )

    with patch.object(backfill, "AsyncSession", return_value=session):
        result = asyncio.run(
            backfill._backfill_topology_preview_batch(
                object(),  # type: ignore[arg-type]
                batch_size=25,
                deferred_graph_ids=frozenset(),
            )
        )

    assert result.generated_count == 1
    assert result.candidate_count == 1
    assert result.deferred_graph_ids == frozenset()
    assert graph.updated_at == original_updated_at
    assert len(session.statements) == 4

    update_statement = session.statements[-1]
    compiled = update_statement.compile(dialect=postgresql.dialect())  # type: ignore[union-attr]
    sql = str(compiled)
    preview = compiled.params["topology_preview"]
    assert preview["nodes"]
    assert {node["color"] for node in preview["nodes"]} == {"slate-blue"}
    assert len(preview["edges"]) == 1
    assert "private" not in repr(preview)
    assert "updated_at=graphs.updated_at" in sql
    assert "now()" not in sql
    assert "graphs.topology_preview = %(topology_preview_1)s::JSONB" in sql


def test_batch_leaves_empty_generated_preview_for_later_startup() -> None:
    graph = _graph()
    session = _BackfillSession(
        [
            _ScalarsResult([graph]),
            _ScalarsResult([_node(position_x=float("nan"))]),
            _ScalarsResult([]),
        ]
    )

    with patch.object(backfill, "AsyncSession", return_value=session):
        result = asyncio.run(
            backfill._backfill_topology_preview_batch(
                object(),  # type: ignore[arg-type]
                batch_size=25,
                deferred_graph_ids=frozenset(),
            )
        )

    assert result.generated_count == 0
    assert result.candidate_count == 1
    assert result.deferred_graph_ids == frozenset({GRAPH_ID})
    assert len(session.statements) == 3
    assert graph.topology_preview == empty_topology_preview_v2()


def test_backfill_revisits_candidate_space_until_none_remain() -> None:
    batch_results = [
        backfill._BackfillBatchResult(
            generated_count=2,
            candidate_count=2,
            deferred_graph_ids=frozenset(),
        ),
        backfill._BackfillBatchResult(
            generated_count=1,
            candidate_count=1,
            deferred_graph_ids=frozenset(),
        ),
        backfill._BackfillBatchResult(
            generated_count=0,
            candidate_count=0,
            deferred_graph_ids=frozenset(),
        ),
    ]

    with patch.object(
        backfill,
        "_backfill_topology_preview_batch",
        new=AsyncMock(side_effect=batch_results),
    ) as process_batch:
        generated_count = asyncio.run(
            backfill.backfill_missing_topology_previews(
                object(),  # type: ignore[arg-type]
                batch_size=2,
            )
        )

    assert generated_count == 3
    assert all(call.kwargs["batch_size"] == 2 for call in process_batch.await_args_list)
    assert [call.kwargs["deferred_graph_ids"] for call in process_batch.await_args_list] == [
        frozenset(),
        frozenset(),
        frozenset(),
    ]

    with patch.object(
        backfill,
        "_backfill_topology_preview_batch",
        new=AsyncMock(
            return_value=backfill._BackfillBatchResult(
                generated_count=0,
                candidate_count=0,
                deferred_graph_ids=frozenset(),
            )
        ),
    ):
        assert (
            asyncio.run(
                backfill.backfill_missing_topology_previews(
                    object(),  # type: ignore[arg-type]
                    batch_size=2,
                )
            )
            == 0
        )


def test_backfill_defers_generated_empty_candidate_without_spinning() -> None:
    batch_results = [
        backfill._BackfillBatchResult(
            generated_count=0,
            candidate_count=1,
            deferred_graph_ids=frozenset({GRAPH_ID}),
        ),
        backfill._BackfillBatchResult(
            generated_count=0,
            candidate_count=0,
            deferred_graph_ids=frozenset(),
        ),
    ]

    with patch.object(
        backfill,
        "_backfill_topology_preview_batch",
        new=AsyncMock(side_effect=batch_results),
    ) as process_batch:
        generated_count = asyncio.run(
            backfill.backfill_missing_topology_previews(
                object(),  # type: ignore[arg-type]
                batch_size=2,
            )
        )

    assert generated_count == 0
    assert [call.kwargs["deferred_graph_ids"] for call in process_batch.await_args_list] == [
        frozenset(),
        frozenset({GRAPH_ID}),
    ]


def test_backfill_rejects_unbounded_zero_batch_size() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        asyncio.run(
            backfill.backfill_missing_topology_previews(
                object(),  # type: ignore[arg-type]
                batch_size=0,
            )
        )


def test_background_runner_logs_and_captures_failure_without_task_exception() -> None:
    failure = RuntimeError("database unavailable")

    with (
        patch.object(
            backfill,
            "backfill_missing_topology_previews",
            new=AsyncMock(side_effect=failure),
        ),
        patch.object(backfill.logger, "error") as log_error,
        patch.object(backfill.sentry_sdk, "capture_exception") as capture_exception,
    ):
        asyncio.run(backfill.run_topology_preview_backfill(object()))  # type: ignore[arg-type]

    capture_exception.assert_called_once_with(failure)
    assert log_error.call_count == 1
    assert "backfill failed" in log_error.call_args.args[0]


def test_background_runner_still_observes_failure_when_error_capture_fails() -> None:
    with (
        patch.object(
            backfill,
            "backfill_missing_topology_previews",
            new=AsyncMock(side_effect=RuntimeError("database unavailable")),
        ),
        patch.object(backfill.logger, "error") as log_error,
        patch.object(
            backfill.sentry_sdk,
            "capture_exception",
            side_effect=RuntimeError("capture unavailable"),
        ),
    ):
        asyncio.run(backfill.run_topology_preview_backfill(object()))  # type: ignore[arg-type]

    assert log_error.call_count == 2


def test_lifespan_registers_backfill_and_awaits_cancellation_on_failed_startup() -> None:
    async def exercise() -> None:
        app = FastAPI()
        engine = AsyncMock()
        backfill_started = asyncio.Event()
        backfill_cancelled = asyncio.Event()

        async def wait_for_cancellation(pg_engine: object) -> None:
            assert pg_engine is engine
            backfill_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                backfill_cancelled.set()

        async def fail_after_backfill_starts(pg_engine: object) -> int:
            assert pg_engine is engine
            await backfill_started.wait()
            raise RuntimeError("stop startup")

        with (
            patch.object(main, "load_environment_variables"),
            patch.object(main, "configure_plan_limits"),
            patch.object(main, "get_pg_async_engine", new=AsyncMock(return_value=engine)),
            patch.object(
                main,
                "run_topology_preview_backfill",
                new=wait_for_cancellation,
            ),
            patch.object(
                main,
                "recover_stale_image_generation_jobs",
                new=fail_after_backfill_starts,
            ),
            patch.object(main.connection_manager, "close", new=AsyncMock()),
            patch.object(main.browser_fetch_manager, "close", new=AsyncMock()),
            pytest.raises(RuntimeError, match="stop startup"),
        ):
            async with main.lifespan(app):
                pytest.fail("lifespan should not reach readiness")

        assert [task.get_name() for task in app.state.background_tasks] == [
            "topology_preview_backfill"
        ]
        assert backfill_cancelled.is_set()
        engine.dispose.assert_awaited_once()

    asyncio.run(exercise())
