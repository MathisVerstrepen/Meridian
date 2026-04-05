from typing import Any, cast

from database.pg.chat_ops import get_tool_calls_by_ids
from database.pg.graph_ops.graph_crud import assert_graph_access
from database.pg.models import PromptImproverRun
from database.pg.prompt_improver_ops import (
    list_prompt_improver_changes_for_run,
    list_prompt_improver_runs_for_node,
)
from models.prompt_improver import (
    PromptImproverAudit,
    PromptImproverChangeRead,
    PromptImproverClarificationRound,
    PromptImproverNodeHistoryResponse,
    PromptImproverRunRead,
    PromptImproverTarget,
    PromptImproverTemplateSnapshot,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

from .context import resolve_targets
from .review import compose_prompt


async def load_clarification_rounds(
    pg_engine: SQLAlchemyAsyncEngine,
    run: PromptImproverRun,
) -> list[PromptImproverClarificationRound]:
    tool_call_ids = [
        tool_call_id
        for tool_call_id in (run.clarification_tool_call_ids or [])
        if isinstance(tool_call_id, str)
    ]
    if not tool_call_ids:
        return []

    tool_calls_by_id = await get_tool_calls_by_ids(
        pg_engine,
        tool_call_ids=tool_call_ids,
        user_id=str(run.user_id),
    )
    rounds: list[PromptImproverClarificationRound] = []
    for tool_call_id in tool_call_ids:
        tool_call = tool_calls_by_id.get(tool_call_id)
        if not tool_call or tool_call.id is None:
            continue
        rounds.append(
            PromptImproverClarificationRound(
                id=str(tool_call.id),
                status=str(tool_call.status),
                arguments=cast(dict[str, Any] | list[Any], tool_call.arguments),
                result=cast(dict[str, Any] | list[Any], tool_call.result),
                created_at=cast(Any, tool_call.created_at),
            )
        )
    return rounds


async def map_run_to_read(
    pg_engine: SQLAlchemyAsyncEngine,
    run: PromptImproverRun,
) -> PromptImproverRunRead:
    changes = await list_prompt_improver_changes_for_run(
        pg_engine,
        run_id=str(run.id),
    )
    clarification_rounds = await load_clarification_rounds(pg_engine, run)
    return PromptImproverRunRead(
        id=str(run.id),
        parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
        node_id=run.node_id,
        target=PromptImproverTarget.model_validate(run.target_snapshot),
        source_prompt=run.source_prompt,
        source_template_snapshot=(
            PromptImproverTemplateSnapshot.model_validate(run.source_template_snapshot)
            if run.source_template_snapshot
            else None
        ),
        selected_dimension_ids=run.selected_dimension_ids or [],
        recommended_dimension_ids=run.recommended_dimension_ids or [],
        audit=PromptImproverAudit.model_validate(run.audit) if run.audit else None,
        improved_prompt=run.improved_prompt,
        composed_prompt=compose_prompt(run.source_prompt, changes),
        feedback=run.feedback,
        status=str(run.status),
        active_phase=run.active_phase,
        active_tool_call_id=run.active_tool_call_id,
        clarification_rounds=clarification_rounds,
        changes=[
            PromptImproverChangeRead(
                id=str(change.id),
                order_index=change.order_index,
                source_start=change.source_start,
                source_end=change.source_end,
                source_text=change.source_text,
                suggested_text=change.suggested_text,
                title=change.title,
                dimension_id=change.dimension_id,
                rationale=change.rationale,
                impact=change.impact,
                review_status=str(change.review_status),
            )
            for change in changes
        ],
        created_at=cast(Any, run.created_at),
        updated_at=cast(Any, run.updated_at),
    )


async def get_prompt_improver_history(
    *,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver,
    graph_id: str,
    node_id: str,
    user_id: str,
    available_models: list[dict[str, Any]] | None,
) -> PromptImproverNodeHistoryResponse:
    await assert_graph_access(pg_engine, graph_id, user_id)
    targets = await resolve_targets(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        user_id=user_id,
        available_models=available_models,
    )
    runs = await list_prompt_improver_runs_for_node(
        pg_engine,
        user_id=user_id,
        graph_id=graph_id,
        node_id=node_id,
    )
    return PromptImproverNodeHistoryResponse(
        targets=targets,
        runs=[await map_run_to_read(pg_engine, run) for run in runs],
    )


def merge_history_runs(
    active_run: PromptImproverRunRead,
    history: list[PromptImproverRunRead],
) -> list[PromptImproverRunRead]:
    return [active_run, *[run for run in history if run.id != active_run.id]]
