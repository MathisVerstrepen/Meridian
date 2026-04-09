import uuid
from typing import Any, TypedDict, cast

from database.pg.models import (
    PromptImproverChange,
    PromptImproverChangeStatusEnum,
    PromptImproverRun,
)
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession


class PromptImproverChangePayload(TypedDict, total=False):
    order_index: int
    source_start: int
    source_end: int
    source_text: str
    suggested_text: str
    title: str | None
    dimension_id: str | None
    rationale: str | None
    impact: str | None
    review_status: str


class PromptImproverReviewPayload(TypedDict):
    change_id: str
    review_status: str


async def create_prompt_improver_run(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    user_id: str,
    graph_id: str,
    node_id: str,
    parent_run_id: str | None,
    target_id: str,
    target_node_id: str | None,
    target_snapshot: dict[str, Any],
    source_prompt: str,
    source_template_snapshot: dict[str, Any] | None,
    selected_dimension_ids: list[str],
    recommended_dimension_ids: list[str],
    audit: dict[str, Any] | None,
    improved_prompt: str | None,
    feedback: str | None,
    active_phase: str | None,
    active_tool_call_id: str | None,
    clarification_tool_call_ids: list[str],
    status: str,
) -> PromptImproverRun:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        run = PromptImproverRun(
            user_id=uuid.UUID(user_id),
            graph_id=uuid.UUID(graph_id),
            node_id=node_id,
            parent_run_id=uuid.UUID(parent_run_id) if parent_run_id else None,
            target_id=target_id,
            target_node_id=target_node_id,
            target_snapshot=target_snapshot,
            source_prompt=source_prompt,
            source_template_snapshot=source_template_snapshot,
            selected_dimension_ids=selected_dimension_ids,
            recommended_dimension_ids=recommended_dimension_ids,
            audit=audit,
            improved_prompt=improved_prompt,
            feedback=feedback,
            active_phase=active_phase,
            active_tool_call_id=active_tool_call_id,
            clarification_tool_call_ids=clarification_tool_call_ids,
            status=status,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def update_prompt_improver_run(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    run_id: str,
    user_id: str,
    **updates: Any,
) -> PromptImproverRun:
    run = await get_prompt_improver_run_by_id(pg_engine, run_id=run_id, user_id=user_id)

    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        persisted = await session.get(PromptImproverRun, run.id)
        if not persisted:
            raise HTTPException(status_code=404, detail="Prompt improver run not found")

        for key, value in updates.items():
            setattr(persisted, key, value)

        session.add(persisted)
        await session.commit()
        await session.refresh(persisted)
        return persisted


async def get_prompt_improver_run_by_id(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    run_id: str,
    user_id: str,
) -> PromptImproverRun:
    try:
        parsed_run_id = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Prompt improver run not found") from exc

    async with AsyncSession(pg_engine) as session:
        stmt = select(PromptImproverRun).where(
            and_(
                PromptImproverRun.id == parsed_run_id,
                PromptImproverRun.user_id == uuid.UUID(user_id),
            )
        )
        result = await session.exec(stmt)  # type: ignore
        run = cast(PromptImproverRun | None, result.scalar_one_or_none())
        if not run:
            raise HTTPException(status_code=404, detail="Prompt improver run not found")
        return run


async def list_prompt_improver_runs_for_node(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    user_id: str,
    graph_id: str,
    node_id: str,
) -> list[PromptImproverRun]:
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(PromptImproverRun)
            .where(
                and_(
                    PromptImproverRun.user_id == uuid.UUID(user_id),
                    PromptImproverRun.graph_id == uuid.UUID(graph_id),
                    PromptImproverRun.node_id == node_id,
                )
            )
            .order_by(PromptImproverRun.created_at.desc())  # type: ignore
        )
        result = await session.exec(stmt)  # type: ignore
        return list(result.scalars().all())


async def create_prompt_improver_changes(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    run_id: str,
    changes: list[PromptImproverChangePayload],
) -> list[PromptImproverChange]:
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        persisted_changes: list[PromptImproverChange] = []
        parsed_run_id = uuid.UUID(run_id)
        for change_payload in changes:
            db_change = PromptImproverChange(
                run_id=parsed_run_id,
                order_index=change_payload["order_index"],
                source_start=change_payload["source_start"],
                source_end=change_payload["source_end"],
                source_text=change_payload["source_text"],
                suggested_text=change_payload["suggested_text"],
                title=change_payload.get("title"),
                dimension_id=change_payload.get("dimension_id"),
                rationale=change_payload.get("rationale"),
                impact=change_payload.get("impact"),
                review_status=change_payload.get(
                    "review_status",
                    PromptImproverChangeStatusEnum.ACCEPTED.value,
                ),
            )
            session.add(db_change)
            persisted_changes.append(db_change)

        await session.commit()

        for persisted_change in persisted_changes:
            await session.refresh(persisted_change)

        return persisted_changes


async def replace_prompt_improver_changes(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    run_id: str,
    changes: list[PromptImproverChangePayload],
) -> list[PromptImproverChange]:
    parsed_run_id = uuid.UUID(run_id)
    async with AsyncSession(pg_engine) as session:
        await session.exec(
            delete(PromptImproverChange).where(
                cast(Any, PromptImproverChange.run_id) == parsed_run_id
            )
        )  # type: ignore
        await session.commit()

    return await create_prompt_improver_changes(
        pg_engine,
        run_id=run_id,
        changes=changes,
    )


async def list_prompt_improver_changes_for_run(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    run_id: str,
) -> list[PromptImproverChange]:
    parsed_run_id = uuid.UUID(run_id)
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(PromptImproverChange)
            .where(cast(Any, PromptImproverChange.run_id) == parsed_run_id)
            .order_by(PromptImproverChange.order_index)  # type: ignore
        )
        result = await session.exec(stmt)  # type: ignore
        return list(result.scalars().all())


async def update_prompt_improver_change_statuses(
    pg_engine: SQLAlchemyAsyncEngine,
    *,
    run_id: str,
    changes: list[PromptImproverReviewPayload],
) -> list[PromptImproverChange]:
    parsed_run_id = uuid.UUID(run_id)
    parsed_change_ids = []
    for change_payload in changes:
        try:
            parsed_change_ids.append(uuid.UUID(change_payload["change_id"]))
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid prompt improver change ID"
            ) from exc

    status_by_id = {
        uuid.UUID(change_payload["change_id"]): PromptImproverChangeStatusEnum(
            change_payload["review_status"]
        )
        for change_payload in changes
    }

    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        stmt = select(PromptImproverChange).where(
            and_(
                PromptImproverChange.run_id == parsed_run_id,
                cast(Any, PromptImproverChange.id).in_(parsed_change_ids),
            )
        )
        result = await session.exec(stmt)  # type: ignore
        persisted_changes = list(result.scalars().all())

        if len(persisted_changes) != len(parsed_change_ids):
            raise HTTPException(status_code=404, detail="Prompt improver change not found")

        for persisted_change in persisted_changes:
            if persisted_change.id is None:
                continue
            persisted_change.review_status = status_by_id[persisted_change.id]
            session.add(persisted_change)

        await session.commit()

        for persisted_change in persisted_changes:
            await session.refresh(persisted_change)

        return sorted(persisted_changes, key=lambda item: item.order_index)
