import copy
import re
import uuid
from typing import Any, cast

from database.pg.models import GenerationHistory, Node
from fastapi import HTTPException
from models.message import NodeTypeEnum
from schemas.generation_history import (
    GenerationHistoryDetail,
    GenerationHistoryEntry,
    GenerationHistoryRestoreResponse,
)
from services.connection_manager import ConnectionManager
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlalchemy.orm import attributes
from sqlmodel import and_, col
from sqlmodel.ext.asyncio.session import AsyncSession

DEFAULT_HISTORY_LIMIT = 10
ACTIVE_HISTORY_ID_KEY = "activeGenerationHistoryId"
SUPPORTED_GENERATION_HISTORY_TYPES = {
    NodeTypeEnum.TEXT_TO_TEXT.value,
    NodeTypeEnum.ROUTING.value,
    NodeTypeEnum.PARALLELIZATION.value,
}


def _parse_uuid_or_400(raw_id: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}.") from exc


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _clean_preview(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= 220:
        return text
    return f"{text[:217]}..."


def _without_active_marker(data: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    data_copy = copy.deepcopy(data)
    if isinstance(data_copy, dict):
        data_copy.pop(ACTIVE_HISTORY_ID_KEY, None)
    return data_copy


def _get_active_history_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    value = data.get(ACTIVE_HISTORY_ID_KEY)
    return value if isinstance(value, str) and value else None


def _set_active_history_id(data: Any, history_id: uuid.UUID | str | None) -> Any:
    if not isinstance(data, dict):
        return data
    if history_id is None:
        data.pop(ACTIVE_HISTORY_ID_KEY, None)
    else:
        data[ACTIVE_HISTORY_ID_KEY] = str(history_id)
    return data


def _extract_generation_snapshot(
    node_type: str,
    data: Any,
) -> tuple[dict[str, Any] | list[Any], str | None, list[str], str, str] | None:
    if node_type not in SUPPORTED_GENERATION_HISTORY_TYPES or not isinstance(data, dict):
        return None

    if node_type in {NodeTypeEnum.TEXT_TO_TEXT.value, NodeTypeEnum.ROUTING.value}:
        reply = data.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            return None

        return (
            _without_active_marker(data),
            data.get("model") if isinstance(data.get("model"), str) else None,
            _coerce_string_list(data.get("selectedTools")),
            _clean_preview(reply),
            reply,
        )

    aggregator = data.get("aggregator")
    if not isinstance(aggregator, dict):
        return None

    reply = aggregator.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        return None

    return (
        _without_active_marker(data),
        aggregator.get("model") if isinstance(aggregator.get("model"), str) else None,
        [],
        _clean_preview(reply),
        reply,
    )


async def _create_generation_history_entry(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    graph_id: uuid.UUID,
    node_id: str,
    node_type: str,
    snapshot: dict[str, Any] | list[Any],
    model: str | None,
    selected_tools: list[str],
    preview: str,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> GenerationHistory:
    history_limit = max(1, history_limit)
    history = GenerationHistory(
        user_id=user_id,
        graph_id=graph_id,
        node_id=node_id,
        node_type=node_type,
        model=model,
        selected_tools=selected_tools,
        preview=preview,
        snapshot=snapshot,
    )
    session.add(history)
    await session.flush()

    old_histories_result = await session.exec(  # type: ignore
        select(GenerationHistory)
        .where(
            and_(
                GenerationHistory.graph_id == graph_id,
                GenerationHistory.node_id == node_id,
            )
        )
        .order_by(col(GenerationHistory.created_at).desc(), col(GenerationHistory.id).desc())
        .offset(history_limit)
    )
    old_ids = [
        old_history.id for old_history in old_histories_result.scalars().all() if old_history.id
    ]
    if old_ids:
        delete_stmt = delete(GenerationHistory).where(col(GenerationHistory.id).in_(old_ids))
        await session.exec(delete_stmt)  # type: ignore

    return history


async def sync_generation_history_for_node_update(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    graph_id: uuid.UUID,
    existing_node: Node,
    incoming_node: Node,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> None:
    old_snapshot = _extract_generation_snapshot(existing_node.type, existing_node.data)
    new_snapshot = _extract_generation_snapshot(incoming_node.type, incoming_node.data)

    incoming_data = copy.deepcopy(incoming_node.data)
    if new_snapshot is None:
        incoming_node.data = _set_active_history_id(incoming_data, None)
        return

    old_output = old_snapshot[4] if old_snapshot else None
    new_output = new_snapshot[4]
    if old_output == new_output:
        active_history_id = _get_active_history_id(existing_node.data)
        incoming_node.data = _set_active_history_id(incoming_data, active_history_id)
        return

    snapshot, model, selected_tools, preview, _ = new_snapshot
    history = await _create_generation_history_entry(
        session,
        user_id=user_id,
        graph_id=graph_id,
        node_id=incoming_node.id,
        node_type=incoming_node.type,
        snapshot=snapshot,
        model=model,
        selected_tools=selected_tools,
        preview=preview,
        history_limit=history_limit,
    )
    incoming_node.data = _set_active_history_id(incoming_data, history.id)


def _to_entry(history: GenerationHistory, active_history_id: str | None) -> GenerationHistoryEntry:
    if history.id is None or history.created_at is None:
        raise HTTPException(status_code=500, detail="Invalid generation history row.")

    return GenerationHistoryEntry(
        id=history.id,
        created_at=history.created_at,
        model=history.model,
        selected_tools=history.selected_tools,
        preview=history.preview,
        is_active=str(history.id) == active_history_id,
    )


async def _get_node_for_generation_history(
    session: AsyncSession,
    *,
    graph_id: uuid.UUID,
    node_id: str,
    with_for_update: bool = False,
) -> Node:
    stmt = select(Node).where(and_(Node.graph_id == graph_id, Node.id == node_id))
    if with_for_update:
        stmt = stmt.with_for_update()

    node_result = await session.exec(stmt)  # type: ignore
    node_any = node_result.scalar_one_or_none()
    if not node_any:
        raise HTTPException(status_code=404, detail="Node not found")
    return cast(Node, node_any)


async def _list_generation_history_entries(
    session: AsyncSession,
    *,
    graph_id: uuid.UUID,
    node_id: str,
    user_id: uuid.UUID,
    active_history_id: str | None,
) -> list[GenerationHistoryEntry]:
    result = await session.exec(  # type: ignore
        select(GenerationHistory)
        .where(
            and_(
                GenerationHistory.graph_id == graph_id,
                GenerationHistory.node_id == node_id,
                GenerationHistory.user_id == user_id,
            )
        )
        .order_by(
            col(GenerationHistory.created_at).desc(),
            col(GenerationHistory.id).desc(),
        )
    )
    histories = result.scalars().all()
    return [_to_entry(history, active_history_id) for history in histories]


async def _backfill_active_generation_history_if_needed(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    graph_id: uuid.UUID,
    node_id: str,
) -> Node:
    node = await _get_node_for_generation_history(
        session,
        graph_id=graph_id,
        node_id=node_id,
        with_for_update=True,
    )

    active_history_id = _get_active_history_id(node.data)
    if active_history_id:
        return node

    existing_history_result = await session.exec(  # type: ignore
        select(GenerationHistory)
        .where(and_(GenerationHistory.graph_id == graph_id, GenerationHistory.node_id == node_id))
        .limit(1)
    )
    if existing_history_result.scalar_one_or_none():
        return node

    extracted = _extract_generation_snapshot(node.type, node.data)
    if extracted is None:
        return node

    snapshot, model, selected_tools, preview, _ = extracted
    history = await _create_generation_history_entry(
        session,
        user_id=user_id,
        graph_id=graph_id,
        node_id=node.id,
        node_type=node.type,
        snapshot=snapshot,
        model=model,
        selected_tools=selected_tools,
        preview=preview,
    )
    node.data = _set_active_history_id(copy.deepcopy(node.data), history.id)
    attributes.flag_modified(node, "data")
    return node


async def ensure_generation_history_backfilled(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    graph_id: str,
    node_id: str,
    user_id: str,
) -> list[GenerationHistoryEntry]:
    graph_uuid = _parse_uuid_or_400(graph_id, "graph ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            node = await _backfill_active_generation_history_if_needed(
                session,
                user_id=user_uuid,
                graph_id=graph_uuid,
                node_id=node_id,
            )
            active_history_id = _get_active_history_id(node.data)
            entries = await _list_generation_history_entries(
                session,
                graph_id=graph_uuid,
                node_id=node_id,
                user_id=user_uuid,
                active_history_id=active_history_id,
            )

    return entries


async def list_generation_history(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    graph_id: str,
    node_id: str,
    user_id: str,
) -> list[GenerationHistoryEntry]:
    graph_uuid = _parse_uuid_or_400(graph_id, "graph ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    async with AsyncSession(pg_engine) as session:
        node = await _get_node_for_generation_history(
            session,
            graph_id=graph_uuid,
            node_id=node_id,
        )
        active_history_id = _get_active_history_id(node.data)
        entries = await _list_generation_history_entries(
            session,
            graph_id=graph_uuid,
            node_id=node_id,
            user_id=user_uuid,
            active_history_id=active_history_id,
        )

    return entries


async def get_generation_history_detail(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    graph_id: str,
    node_id: str,
    history_id: str,
    user_id: str,
) -> GenerationHistoryDetail:
    graph_uuid = _parse_uuid_or_400(graph_id, "graph ID")
    history_uuid = _parse_uuid_or_400(history_id, "history ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    async with AsyncSession(pg_engine) as session:
        node_result = await session.exec(  # type: ignore
            select(Node).where(and_(Node.graph_id == graph_uuid, Node.id == node_id))
        )
        node = node_result.scalar_one_or_none()
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        result = await session.exec(  # type: ignore
            select(GenerationHistory).where(
                and_(
                    GenerationHistory.id == history_uuid,
                    GenerationHistory.graph_id == graph_uuid,
                    GenerationHistory.node_id == node_id,
                    GenerationHistory.user_id == user_uuid,
                )
            )
        )
        history = result.scalar_one_or_none()
        if not history:
            raise HTTPException(status_code=404, detail="Generation history entry not found")

        entry = _to_entry(history, _get_active_history_id(node.data))
        detail = GenerationHistoryDetail(**entry.model_dump(), snapshot=history.snapshot)

    return detail


async def restore_generation_history(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    graph_id: str,
    node_id: str,
    history_id: str,
    user_id: str,
    connection_manager: ConnectionManager | None = None,
) -> GenerationHistoryRestoreResponse:
    graph_uuid = _parse_uuid_or_400(graph_id, "graph ID")
    history_uuid = _parse_uuid_or_400(history_id, "history ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            result = await session.exec(  # type: ignore
                select(GenerationHistory).where(
                    and_(
                        GenerationHistory.id == history_uuid,
                        GenerationHistory.graph_id == graph_uuid,
                        GenerationHistory.node_id == node_id,
                        GenerationHistory.user_id == user_uuid,
                    )
                )
            )
            history = result.scalar_one_or_none()
            if not history:
                raise HTTPException(status_code=404, detail="Generation history entry not found")

            node_result = await session.exec(  # type: ignore
                select(Node)
                .where(and_(Node.graph_id == graph_uuid, Node.id == node_id))
                .with_for_update()
            )
            node = node_result.scalar_one_or_none()
            if not node:
                raise HTTPException(status_code=404, detail="Node not found")

            node_data = _set_active_history_id(copy.deepcopy(history.snapshot), history.id)
            node.data = node_data
            attributes.flag_modified(node, "data")

    if connection_manager:
        await connection_manager.send_to_user(
            str(user_uuid),
            {
                "type": "node_data_replace",
                "graph_id": str(graph_uuid),
                "node_id": node_id,
                "payload": node_data,
            },
        )

    return GenerationHistoryRestoreResponse(node_data=node_data)
