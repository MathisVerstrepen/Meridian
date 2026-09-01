import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

import sentry_sdk
from database.pg.models import Edge, Graph, Node
from schemas.topology_preview import empty_topology_preview_v2
from services.graph_topology_preview import build_topology_preview
from sqlalchemy import exists, update
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")
TOPOLOGY_PREVIEW_BACKFILL_BATCH_SIZE = 25


@dataclass(frozen=True)
class _BackfillBatchResult:
    generated_count: int
    candidate_count: int
    deferred_graph_ids: frozenset[uuid.UUID]


def _candidate_statement(
    *,
    batch_size: int,
    deferred_graph_ids: frozenset[uuid.UUID],
) -> Any:
    statement = (
        select(Graph)
        .where(col(Graph.topology_preview) == empty_topology_preview_v2())
        .where(exists(select(col(Node.id)).where(col(Node.graph_id) == col(Graph.id))))
        .order_by(col(Graph.id))
        .limit(batch_size)
        .with_for_update(of=Graph)
    )
    if deferred_graph_ids:
        statement = statement.where(col(Graph.id).not_in(sorted(deferred_graph_ids)))
    return statement


def _preview_update_statement(graph_id: uuid.UUID, preview: dict[str, Any]) -> Any:
    return (
        update(Graph)
        .where(col(Graph.id) == graph_id)
        .where(col(Graph.topology_preview) == empty_topology_preview_v2())
        .values(
            topology_preview=preview,
            updated_at=col(Graph.updated_at),
        )
    )


async def _backfill_topology_preview_batch(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    batch_size: int,
    deferred_graph_ids: frozenset[uuid.UUID],
) -> _BackfillBatchResult:
    generated_count = 0
    newly_deferred_graph_ids: set[uuid.UUID] = set()

    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            candidate_result = await session.exec(
                _candidate_statement(
                    batch_size=batch_size,
                    deferred_graph_ids=deferred_graph_ids,
                )
            )
            candidates = list(candidate_result.all())

            for graph in candidates:
                graph_id = graph.id
                if graph_id is None:
                    raise ValueError("Persisted graph candidate has no ID")

                node_result = await session.exec(select(Node).where(col(Node.graph_id) == graph_id))
                edge_result = await session.exec(select(Edge).where(col(Edge.graph_id) == graph_id))
                nodes = list(node_result.all())
                edges = list(edge_result.all())

                preview = build_topology_preview(nodes, edges)
                if not preview.nodes:
                    newly_deferred_graph_ids.add(graph_id)
                    continue

                await session.exec(
                    _preview_update_statement(
                        graph_id,
                        preview.model_dump(mode="json"),
                    )
                )
                generated_count += 1

    return _BackfillBatchResult(
        generated_count=generated_count,
        candidate_count=len(candidates),
        deferred_graph_ids=frozenset(newly_deferred_graph_ids),
    )


async def backfill_missing_topology_previews(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    batch_size: int = TOPOLOGY_PREVIEW_BACKFILL_BATCH_SIZE,
) -> int:
    if batch_size < 1:
        raise ValueError("Topology preview backfill batch size must be positive")

    generated_count = 0
    deferred_graph_ids: set[uuid.UUID] = set()

    while True:
        batch = await _backfill_topology_preview_batch(
            pg_engine,
            batch_size=batch_size,
            deferred_graph_ids=frozenset(deferred_graph_ids),
        )
        generated_count += batch.generated_count
        deferred_graph_ids.update(batch.deferred_graph_ids)
        if batch.candidate_count == 0:
            return generated_count


async def run_topology_preview_backfill(pg_engine: SQLAlchemyAsyncEngine) -> None:
    try:
        generated_count = await backfill_missing_topology_previews(pg_engine)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(
            "Startup topology preview backfill failed: %s",
            exc,
            exc_info=True,
        )
        try:
            sentry_sdk.capture_exception(exc)
        except Exception:
            logger.error(
                "Failed to capture startup topology preview backfill error",
                exc_info=True,
            )
        return

    logger.info(
        "Startup topology preview backfill complete: generated %s previews.",
        generated_count,
    )
