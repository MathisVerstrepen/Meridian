import uuid
from typing import Any, cast

from database.pg.models import ToolCall, ToolCallStatusEnum
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_tool_call(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    user_id: str,
    graph_id: str,
    node_id: str,
    tool_name: str,
    status: ToolCallStatusEnum,
    arguments: dict[str, Any] | list[Any],
    result: dict[str, Any] | list[Any],
    model_context_payload: str,
    model_id: str | None = None,
    tool_call_id: str | None = None,
) -> ToolCall:
    async with AsyncSession(pg_engine) as session:
        tool_call = ToolCall(
            user_id=uuid.UUID(user_id),
            graph_id=uuid.UUID(graph_id),
            node_id=node_id,
            model_id=model_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            arguments=arguments,
            result=result,
            model_context_payload=model_context_payload,
        )
        session.add(tool_call)
        await session.commit()
        await session.refresh(tool_call)
        return tool_call


async def get_tool_call_by_id(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    tool_call_id: str,
    user_id: str,
) -> ToolCall:
    try:
        parsed_tool_call_id = uuid.UUID(tool_call_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Tool call not found") from exc

    async with AsyncSession(pg_engine) as session:
        stmt = select(ToolCall).where(
            and_(ToolCall.id == parsed_tool_call_id, ToolCall.user_id == uuid.UUID(user_id))
        )
        result = await session.exec(stmt)  # type: ignore
        tool_call = cast(ToolCall | None, result.scalar_one_or_none())
        if not tool_call:
            raise HTTPException(status_code=404, detail="Tool call not found")
        return tool_call


async def get_tool_calls_by_ids(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    tool_call_ids: list[str],
    user_id: str,
) -> dict[str, ToolCall]:
    if not tool_call_ids:
        return {}

    parsed_ids: list[uuid.UUID] = []
    for tool_call_id in tool_call_ids:
        try:
            parsed_ids.append(uuid.UUID(tool_call_id))
        except ValueError:
            continue

    if not parsed_ids:
        return {}

    async with AsyncSession(pg_engine) as session:
        tool_call_id_column = cast(Any, ToolCall.id)
        stmt = select(ToolCall).where(
            and_(
                tool_call_id_column.in_(parsed_ids),
                ToolCall.user_id == uuid.UUID(user_id),
            )
        )
        result = await session.exec(stmt)  # type: ignore
        tool_calls = result.scalars().all()
        return {
            str(tool_call.id): tool_call for tool_call in tool_calls if tool_call.id is not None
        }
